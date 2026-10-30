# Pet Shop Recommendation API
# Учебный прототип backend: данные хранятся в памяти процесса,
# внешний платёжный сервис имитируется ручным вызовом webhook.

import copy
from datetime import date
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(
    title="Pet Shop Recommendation API",
    description=(
        "API интернет-магазина товаров для домашних животных "
        "с функцией персонализированных рекомендаций."
    ),
    version="1.1.0",
)

# Допустимые значения справочных полей.
# Literal показывает их в Swagger и проверяет входные данные.
Species = Literal["cat", "dog"]
ActivityLevel = Literal["low", "normal", "high"]
Size = Literal["small", "medium", "large"]
WebhookPaymentStatus = Literal["PAID", "PAYMENT_FAILED"]


# Исходный каталог и справочник ингредиентов.
# Каталог копируется в рабочий список при каждом сбросе данных,
# поэтому тесты можно запускать повторно с одного и того же состояния.

INITIAL_PRODUCTS = [
    {
        "id": 101,
        "name": "Adult Cat Beef",
        "description": "Сухой корм для взрослых кошек с говядиной",
        "category": "food",
        "species": "cat",
        "price": 1290,
        "available": True,
        "stockQuantity": 15,
        "minAgeMonths": 12,
        "maxAgeMonths": None,
        "activityLevel": "normal",
        "size": None,
        "ingredientIds": [1, 2],
    },
    {
        "id": 102,
        "name": "Adult Cat Chicken",
        "description": "Сухой корм для взрослых кошек с курицей",
        "category": "food",
        "species": "cat",
        "price": 1190,
        "available": True,
        "stockQuantity": 10,
        "minAgeMonths": 12,
        "maxAgeMonths": None,
        "activityLevel": "normal",
        "size": None,
        "ingredientIds": [2, 3],
    },
    {
        "id": 103,
        "name": "Cat Salmon Active",
        "description": "Корм для активных взрослых кошек с лососем",
        "category": "food",
        "species": "cat",
        "price": 1490,
        "available": True,
        "stockQuantity": 8,
        "minAgeMonths": 12,
        "maxAgeMonths": None,
        "activityLevel": "high",
        "size": None,
        "ingredientIds": [2, 5],
    },
    {
        "id": 104,
        "name": "Dog Ball",
        "description": "Игрушка-мяч для собак среднего размера",
        "category": "toy",
        "species": "dog",
        "price": 490,
        "available": True,
        "stockQuantity": 20,
        "minAgeMonths": None,
        "maxAgeMonths": None,
        "activityLevel": None,
        "size": "medium",
        "ingredientIds": [],
    },
    {
        "id": 105,
        "name": "Cat Toy Mouse",
        "description": "Игрушка-мышь для кошек",
        "category": "toy",
        "species": "cat",
        "price": 350,
        "available": False,
        "stockQuantity": 0,
        "minAgeMonths": None,
        "maxAgeMonths": None,
        "activityLevel": None,
        "size": None,
        "ingredientIds": [],
    },
    {
        "id": 106,
        "name": "Cat Tunnel",
        "description": "Игровой тоннель для кошек среднего размера",
        "category": "toy",
        "species": "cat",
        "price": 790,
        "available": True,
        "stockQuantity": 5,
        "minAgeMonths": None,
        "maxAgeMonths": None,
        "activityLevel": None,
        "size": "medium",
        "ingredientIds": [],
    },
]

ingredients = [
    {"id": 1, "name": "Говядина"},
    {"id": 2, "name": "Рис"},
    {"id": 3, "name": "Курица"},
    {"id": 4, "name": "Индейка"},
    {"id": 5, "name": "Лосось"},
]

SPECIES_NAMES = {"cat": "кошек", "dog": "собак"}


# Хранилища в памяти. reset_data() возвращает их в исходное состояние.

def reset_data():
    global products, pets, cart, orders, payments
    global next_pet_id, next_cart_item_id, next_order_id, next_payment_id

    products = copy.deepcopy(INITIAL_PRODUCTS)
    pets = {}
    cart = {}
    orders = {}
    payments = {}

    next_pet_id = 1
    next_cart_item_id = 1
    next_order_id = 5001
    next_payment_id = 9001


reset_data()


# Модели запросов и ответов (Pydantic).
# Примеры из json_schema_extra отображаются в Swagger как тело запроса по умолчанию.

class ErrorResponse(BaseModel):
    detail: str


class IngredientResponse(BaseModel):
    id: int
    name: str


class PetCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "name": "Барсик",
        "species": "cat",
        "birthDate": "2022-05-15",
        "weight": 4.5,
        "size": "medium",
        "activityLevel": "normal",
        "excludedIngredientIds": [3],
    }]})

    name: str = Field(min_length=1)
    species: Species
    birthDate: date
    weight: Optional[float] = Field(default=None, gt=0)
    size: Optional[Size] = None
    activityLevel: Optional[ActivityLevel] = None
    excludedIngredientIds: list[int] = []


class PetUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "activityLevel": "high",
        "excludedIngredientIds": [3, 5],
    }]})

    name: Optional[str] = Field(default=None, min_length=1)
    species: Optional[Species] = None
    birthDate: Optional[date] = None
    weight: Optional[float] = Field(default=None, gt=0)
    size: Optional[Size] = None
    activityLevel: Optional[ActivityLevel] = None
    excludedIngredientIds: Optional[list[int]] = None


class PetResponse(BaseModel):
    id: int
    name: str
    species: Species
    birthDate: date
    weight: Optional[float] = None
    size: Optional[Size] = None
    activityLevel: Optional[ActivityLevel] = None
    excludedIngredientIds: list[int] = []


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    species: Species
    price: float
    available: bool
    stockQuantity: int
    minAgeMonths: Optional[int] = None
    maxAgeMonths: Optional[int] = None
    activityLevel: Optional[ActivityLevel] = None
    size: Optional[Size] = None
    ingredientIds: list[int]


class RecommendationItem(BaseModel):
    productId: int
    name: str
    category: str
    price: float
    score: int
    reasons: list[str]


class RecommendationResponse(BaseModel):
    petId: int
    petName: str
    recommendations: list[RecommendationItem]


class CartItemCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "productId": 101,
        "quantity": 2,
    }]})

    productId: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"quantity": 3}]})

    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    itemId: int
    productId: int
    quantity: int


class CartViewItem(BaseModel):
    itemId: int
    productId: int
    name: str
    quantity: int
    price: float
    total: float


class CartResponse(BaseModel):
    items: list[CartViewItem]
    totalAmount: float


class OrderCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "deliveryAddress": "Санкт-Петербург, Невский проспект, 10",
    }]})

    deliveryAddress: str = Field(min_length=1)


class OrderItem(BaseModel):
    productId: int
    name: str
    quantity: int
    price: float


class OrderResponse(BaseModel):
    orderId: int
    status: str
    paymentStatus: str
    externalPaymentId: str
    deliveryAddress: str
    totalAmount: float
    items: list[OrderItem]


class OrderCreateResponse(OrderResponse):
    paymentUrl: str


class PaymentWebhook(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "externalPaymentId": "pay_9001",
        "orderId": 5001,
        "status": "PAID",
    }]})

    externalPaymentId: str
    orderId: int
    status: WebhookPaymentStatus


class PaymentWebhookResponse(BaseModel):
    status: Literal["accepted", "already_processed"]
    orderId: int
    orderStatus: str


# Вспомогательные функции

def error(status_code: int, detail: str):
    """Описание ошибки для параметра responses в декораторе (попадает в OpenAPI)."""
    return {status_code: {"model": ErrorResponse, "description": detail}}


def get_product_or_404(product_id: int):
    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def get_pet_or_404(pet_id: int):
    if pet_id not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pets[pet_id]


def age_in_months(birth_date: date) -> int:
    today = date.today()
    months = (today.year - birth_date.year) * 12 + today.month - birth_date.month
    if today.day < birth_date.day:
        months -= 1  # полный месяц ещё не прошёл
    return months


def validate_pet_fields(fields: dict):
    """Проверки, которые нельзя выразить типами Pydantic."""
    if fields.get("birthDate") and fields["birthDate"] > date.today():
        raise HTTPException(status_code=422, detail="Birth date cannot be in the future")

    known_ids = {i["id"] for i in ingredients}
    unknown = sorted(set(fields.get("excludedIngredientIds") or []) - known_ids)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown ingredient ids: {unknown}")


def check_stock(product: dict, quantity: int):
    if not product["available"] or product["stockQuantity"] <= 0:
        raise HTTPException(status_code=409, detail=f"Product {product['name']} is not available")
    if quantity > product["stockQuantity"]:
        raise HTTPException(
            status_code=409,
            detail=f"Not enough stock for {product['name']}: available {product['stockQuantity']}",
        )


def order_to_response(order: dict) -> dict:
    """Статус оплаты берётся из связанного платежа, а не хранится в заказе повторно."""
    payment = payments[order["externalPaymentId"]]
    return {**order, "paymentStatus": payment["status"]}


# Алгоритм рекомендаций.
# Шаг 1 — жёсткие фильтры: неподходящий товар не попадает в подборку.
# Шаг 2 — ранжирование по «мягким» критериям: баллы различают товары, прошедшие фильтр.

SCORE_ACTIVITY = 2  # уровень активности питомца совпадает с назначением товара
SCORE_SIZE = 1      # размер питомца совпадает с размером, на который рассчитан товар


def calculate_recommendations(pet: dict) -> list[dict]:
    pet_age = age_in_months(pet["birthDate"])
    excluded = set(pet.get("excludedIngredientIds") or [])

    recommendations = []

    for product in products:
        # --- Жёсткие фильтры ---
        if not product["available"] or product["stockQuantity"] <= 0:
            continue
        if product["species"] != pet["species"]:
            continue

        min_age = product["minAgeMonths"]
        max_age = product["maxAgeMonths"]
        if min_age is not None and pet_age < min_age:
            continue
        if max_age is not None and pet_age > max_age:
            continue

        if excluded & set(product["ingredientIds"]):
            continue

        # Причины, по которым товар прошёл фильтр (баллы за них не начисляются)
        reasons = [f"Предназначен для {SPECIES_NAMES[pet['species']]}"]
        if min_age is not None or max_age is not None:
            reasons.append("Подходит по возрасту")
        if excluded and product["category"] == "food":
            reasons.append("Не содержит исключённых ингредиентов")

        # --- Ранжирование ---
        score = 0
        if pet.get("activityLevel") and pet["activityLevel"] == product["activityLevel"]:
            score += SCORE_ACTIVITY
            reasons.append("Соответствует уровню активности")
        if pet.get("size") and pet["size"] == product["size"]:
            score += SCORE_SIZE
            reasons.append("Подходит по размеру")

        recommendations.append({
            "productId": product["id"],
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "score": score,
            "reasons": reasons,
        })

    # По убыванию балла; при равенстве — сначала более дешёвый товар
    recommendations.sort(key=lambda item: (-item["score"], item["price"]))
    return recommendations


# Питомцы и справочник ингредиентов

@app.get(
    "/ingredients",
    response_model=list[IngredientResponse],
    tags=["Справочники"],
    summary="Получить справочник ингредиентов",
    description="Возвращает ингредиенты, которые можно указать как нежелательные в профиле питомца.",
)
def get_ingredients():
    return ingredients


@app.get(
    "/pets",
    response_model=list[PetResponse],
    tags=["Питомцы"],
    summary="Получить список питомцев",
    description="Возвращает все созданные профили питомцев.",
)
def get_pets():
    return list(pets.values())


@app.post(
    "/pets",
    response_model=PetResponse,
    status_code=201,
    tags=["Питомцы"],
    summary="Создать профиль питомца",
    description=(
        "Создаёт профиль питомца для персональных рекомендаций. "
        "Дата рождения не может быть в будущем; идентификаторы ингредиентов "
        "должны существовать в справочнике GET /ingredients."
    ),
)
def create_pet(data: PetCreate):
    global next_pet_id

    fields = data.model_dump()
    validate_pet_fields(fields)

    pet = {"id": next_pet_id, **fields}
    pets[next_pet_id] = pet
    next_pet_id += 1
    return pet


@app.patch(
    "/pets/{pet_id}",
    response_model=PetResponse,
    tags=["Питомцы"],
    summary="Изменить профиль питомца",
    description="Частично изменяет профиль: обновляются только переданные поля.",
    responses=error(404, "Питомец не найден"),
)
def update_pet(pet_id: int, data: PetUpdate):
    pet = get_pet_or_404(pet_id)

    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "species", "birthDate"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"Field {field} cannot be null")
    validate_pet_fields(changes)

    pet.update(changes)
    return pet


# Каталог

@app.get(
    "/products",
    response_model=list[ProductResponse],
    tags=["Каталог"],
    summary="Получить каталог товаров",
    description="Возвращает список товаров интернет-магазина.",
)
def get_products():
    return products


@app.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    tags=["Каталог"],
    summary="Получить карточку товара",
    description="Возвращает подробную информацию о выбранном товаре.",
    responses=error(404, "Товар не найден"),
)
def get_product(product_id: int):
    return get_product_or_404(product_id)


# Рекомендации

@app.get(
    "/pets/{pet_id}/recommendations",
    response_model=RecommendationResponse,
    tags=["Рекомендации"],
    summary="Получить персональные рекомендации",
    description=(
        "Формирует подборку товаров для питомца: исключает недоступные товары, "
        "товары для другого вида, вне возрастного диапазона и с исключёнными "
        "ингредиентами, затем сортирует по баллу соответствия. "
        "Пустой список — штатный результат."
    ),
    responses=error(404, "Питомец не найден"),
)
def get_recommendations(pet_id: int):
    pet = get_pet_or_404(pet_id)
    return {
        "petId": pet["id"],
        "petName": pet["name"],
        "recommendations": calculate_recommendations(pet),
    }


# Корзина

@app.get(
    "/cart",
    response_model=CartResponse,
    tags=["Корзина"],
    summary="Получить корзину",
    description="Возвращает позиции корзины и итоговую стоимость.",
)
def get_cart():
    items = []
    for item in cart.values():
        product = get_product_or_404(item["productId"])
        items.append({
            "itemId": item["itemId"],
            "productId": product["id"],
            "name": product["name"],
            "quantity": item["quantity"],
            "price": product["price"],
            "total": product["price"] * item["quantity"],
        })
    return {"items": items, "totalAmount": sum(i["total"] for i in items)}


@app.post(
    "/cart/items",
    response_model=CartItemResponse,
    status_code=201,
    tags=["Корзина"],
    summary="Добавить товар в корзину",
    description=(
        "Добавляет товар в корзину. Если товар уже есть в корзине, "
        "увеличивается количество в существующей позиции; "
        "суммарное количество не может превышать остаток."
    ),
    responses={
        **error(404, "Товар не найден"),
        **error(409, "Товар недоступен или недостаточно остатка"),
    },
)
def add_cart_item(data: CartItemCreate):
    global next_cart_item_id

    product = get_product_or_404(data.productId)
    existing = next((i for i in cart.values() if i["productId"] == data.productId), None)

    new_quantity = data.quantity + (existing["quantity"] if existing else 0)
    check_stock(product, new_quantity)

    if existing:
        existing["quantity"] = new_quantity
        return existing

    item = {"itemId": next_cart_item_id, "productId": data.productId, "quantity": data.quantity}
    cart[next_cart_item_id] = item
    next_cart_item_id += 1
    return item


@app.patch(
    "/cart/items/{item_id}",
    response_model=CartItemResponse,
    tags=["Корзина"],
    summary="Изменить количество товара",
    description="Устанавливает новое количество товара в позиции корзины.",
    responses={
        **error(404, "Позиция корзины не найдена"),
        **error(409, "Товар недоступен или недостаточно остатка"),
    },
)
def update_cart_item(item_id: int, data: CartItemUpdate):
    if item_id not in cart:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product = get_product_or_404(cart[item_id]["productId"])
    check_stock(product, data.quantity)

    cart[item_id]["quantity"] = data.quantity
    return cart[item_id]


@app.delete(
    "/cart/items/{item_id}",
    status_code=204,
    tags=["Корзина"],
    summary="Удалить товар из корзины",
    description="Удаляет позицию из корзины.",
    responses=error(404, "Позиция корзины не найдена"),
)
def delete_cart_item(item_id: int):
    if item_id not in cart:
        raise HTTPException(status_code=404, detail="Cart item not found")
    del cart[item_id]
    return Response(status_code=204)


# Заказы

@app.post(
    "/orders",
    response_model=OrderCreateResponse,
    status_code=201,
    tags=["Заказы"],
    summary="Создать заказ",
    description=(
        "Создаёт заказ из текущей корзины со статусом WAITING_PAYMENT, "
        "регистрирует платёж (заглушка внешнего сервиса) и очищает корзину."
    ),
    responses={
        **error(400, "Корзина пуста"),
        **error(409, "Товар недоступен или недостаточно остатка"),
    },
)
def create_order(data: OrderCreate):
    global next_order_id, next_payment_id

    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order_items = []
    total_amount = 0
    for item in cart.values():
        product = get_product_or_404(item["productId"])
        check_stock(product, item["quantity"])
        order_items.append({
            "productId": product["id"],
            "name": product["name"],
            "quantity": item["quantity"],
            "price": product["price"],
        })
        total_amount += product["price"] * item["quantity"]

    order_id = next_order_id
    next_order_id += 1
    external_payment_id = f"pay_{next_payment_id}"
    next_payment_id += 1

    order = {
        "orderId": order_id,
        "status": "WAITING_PAYMENT",
        "externalPaymentId": external_payment_id,
        "deliveryAddress": data.deliveryAddress,
        "totalAmount": total_amount,
        "items": order_items,
    }
    payments[external_payment_id] = {
        "externalPaymentId": external_payment_id,
        "orderId": order_id,
        "status": "WAITING_PAYMENT",
        "amount": total_amount,
    }
    orders[order_id] = order
    cart.clear()

    return {
        **order_to_response(order),
        "paymentUrl": f"https://payment.example/pay/{external_payment_id}",
    }


@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    tags=["Заказы"],
    summary="Получить заказ",
    description="Возвращает заказ, его статус и статус оплаты.",
    responses=error(404, "Заказ не найден"),
)
def get_order(order_id: int):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_response(orders[order_id])


# Интеграция с платёжным сервисом (webhook)

@app.post(
    "/payments/webhook",
    response_model=PaymentWebhookResponse,
    tags=["Оплата"],
    summary="Обработать уведомление об оплате",
    description=(
        "Имитация webhook внешнего платёжного сервиса. "
        "PAID переводит заказ в PAID и списывает остатки, "
        "PAYMENT_FAILED переводит заказ в PAYMENT_FAILED. "
        "Повторное уведомление по уже обработанному платежу ничего не меняет "
        "и возвращает status = already_processed (идемпотентность)."
    ),
    responses={
        **error(400, "Платёж не относится к указанному заказу"),
        **error(404, "Платёж не найден"),
    },
)
def payment_webhook(data: PaymentWebhook):
    payment = payments.get(data.externalPaymentId)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment["orderId"] != data.orderId:
        raise HTTPException(status_code=400, detail="Payment does not belong to this order")

    order = orders[data.orderId]

    # Повторная доставка уведомления не должна повторно списывать остатки
    if payment["status"] != "WAITING_PAYMENT":
        return {"status": "already_processed", "orderId": order["orderId"], "orderStatus": order["status"]}

    payment["status"] = data.status
    order["status"] = data.status

    if data.status == "PAID":
        for item in order["items"]:
            product = get_product_or_404(item["productId"])
            product["stockQuantity"] = max(product["stockQuantity"] - item["quantity"], 0)
            if product["stockQuantity"] == 0:
                product["available"] = False

    return {"status": "accepted", "orderId": order["orderId"], "orderStatus": order["status"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
