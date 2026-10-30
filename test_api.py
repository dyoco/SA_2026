# Автоматическая проверка API без запуска сервера (TestClient).
# Каждая проверка начинается с reset_data(), в конце данные снова сбрасываются.

from fastapi.testclient import TestClient

from main import app, reset_data

client = TestClient(app)


def check(name, condition):
    assert condition, f"Проверка не пройдена: {name}"
    print(f"OK  {name}")


def run_api_checks():
    reset_data()

    # 1. Профиль питомца и рекомендации
    r = client.post("/pets", json={
        "name": "Барсик", "species": "cat", "birthDate": "2022-05-15",
        "size": "medium", "activityLevel": "normal", "excludedIngredientIds": [3],
    })
    check("POST /pets → 201", r.status_code == 201)
    pet_id = r.json()["id"]

    r = client.get("/ingredients")
    check("GET /ingredients → 5 ингредиентов", r.status_code == 200 and len(r.json()) == 5)

    recs = client.get(f"/pets/{pet_id}/recommendations").json()["recommendations"]
    ids = [x["productId"] for x in recs]
    check("Рекомендации: курица (id 3) исключена — нет товара 102", 102 not in ids)
    check("Рекомендации: недоступная игрушка 105 не рекомендуется", 105 not in ids)
    check("Рекомендации: товар для собак 104 не рекомендуется", 104 not in ids)
    check("Рекомендации: порядок 101 → 106 → 103", ids == [101, 106, 103])

    r = client.patch(f"/pets/{pet_id}", json={"activityLevel": "high"})
    check("PATCH /pets/{id} → 200", r.status_code == 200)
    ids = [x["productId"] for x in client.get(f"/pets/{pet_id}/recommendations").json()["recommendations"]]
    check("После смены активности первым идёт 103 (Cat Salmon Active)", ids[0] == 103)

    check("404 для неизвестного питомца", client.get("/pets/999/recommendations").status_code == 404)
    check("422 для неизвестного ингредиента",
          client.patch(f"/pets/{pet_id}", json={"excludedIngredientIds": [42]}).status_code == 422)
    check("422 для даты рождения в будущем",
          client.patch(f"/pets/{pet_id}", json={"birthDate": "2999-01-01"}).status_code == 422)
    check("422 для недопустимого вида животного",
          client.patch(f"/pets/{pet_id}", json={"species": "fish"}).status_code == 422)

    # 2. Каталог и корзина
    check("GET /products/101 → 200", client.get("/products/101").status_code == 200)
    check("404 для неизвестного товара", client.get("/products/999").status_code == 404)
    check("409 при добавлении недоступного товара",
          client.post("/cart/items", json={"productId": 105, "quantity": 1}).status_code == 409)

    item = client.post("/cart/items", json={"productId": 101, "quantity": 10}).json()
    r = client.post("/cart/items", json={"productId": 101, "quantity": 10})
    check("409, если суммарное количество в корзине превышает остаток (10 + 10 > 15)", r.status_code == 409)
    r = client.post("/cart/items", json={"productId": 101, "quantity": 2})
    check("Повторное добавление увеличивает существующую позицию", r.json()["itemId"] == item["itemId"]
          and r.json()["quantity"] == 12)
    check("PATCH /cart/items/{id} → 200",
          client.patch(f"/cart/items/{item['itemId']}", json={"quantity": 2}).status_code == 200)
    extra = client.post("/cart/items", json={"productId": 106, "quantity": 1}).json()
    check("DELETE /cart/items/{id} → 204",
          client.delete(f"/cart/items/{extra['itemId']}").status_code == 204)
    check("GET /cart: 2 × 1290 = 2580", client.get("/cart").json()["totalAmount"] == 2580)

    # 3. Заказ и оплата
    order = client.post("/orders", json={"deliveryAddress": "Санкт-Петербург, Невский проспект, 10"})
    check("POST /orders → 201, статус WAITING_PAYMENT",
          order.status_code == 201 and order.json()["status"] == "WAITING_PAYMENT")
    order = order.json()
    check("Корзина очищена после оформления", client.get("/cart").json()["items"] == [])
    check("400 при оформлении пустой корзины",
          client.post("/orders", json={"deliveryAddress": "x"}).status_code == 400)

    webhook = {"externalPaymentId": order["externalPaymentId"], "orderId": order["orderId"], "status": "PAID"}
    r = client.post("/payments/webhook", json=webhook)
    check("Webhook PAID → accepted, заказ PAID",
          r.json()["status"] == "accepted" and r.json()["orderStatus"] == "PAID")
    check("Остаток товара 101 уменьшился с 15 до 13", client.get("/products/101").json()["stockQuantity"] == 13)

    r = client.post("/payments/webhook", json={**webhook, "status": "PAYMENT_FAILED"})
    check("Повторный webhook → already_processed, статус не изменился",
          r.json()["status"] == "already_processed" and r.json()["orderStatus"] == "PAID")
    check("Повторный webhook не списал остаток повторно",
          client.get("/products/101").json()["stockQuantity"] == 13)
    r = client.get(f"/orders/{order['orderId']}").json()
    check("GET /orders/{id}: status = PAID, paymentStatus = PAID",
          r["status"] == "PAID" and r["paymentStatus"] == "PAID")

    check("404 для неизвестного платежа",
          client.post("/payments/webhook", json={**webhook, "externalPaymentId": "pay_0"}).status_code == 404)
    check("400, если платёж не относится к заказу",
          client.post("/payments/webhook", json={**webhook, "orderId": 1}).status_code == 400)

    # 4. Неуспешная оплата
    client.post("/cart/items", json={"productId": 103, "quantity": 1})
    order2 = client.post("/orders", json={"deliveryAddress": "Москва, Тверская, 1"}).json()
    r = client.post("/payments/webhook", json={
        "externalPaymentId": order2["externalPaymentId"], "orderId": order2["orderId"], "status": "PAYMENT_FAILED",
    })
    check("Webhook PAYMENT_FAILED → заказ PAYMENT_FAILED", r.json()["orderStatus"] == "PAYMENT_FAILED")
    check("При неуспешной оплате остаток не списан", client.get("/products/103").json()["stockQuantity"] == 8)
    check("422 для неподдерживаемого статуса оплаты",
          client.post("/payments/webhook", json={**webhook, "status": "REFUNDED"}).status_code == 422)

    reset_data()
    print("\nВсе проверки пройдены.")


def test_api():
    """Точка входа для pytest."""
    run_api_checks()


if __name__ == "__main__":
    run_api_checks()
