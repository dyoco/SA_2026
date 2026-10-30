from main import app

# Выгрузка OpenAPI-спецификации в файлы для сдачи (openapi.json и openapi.yaml)

import json
import yaml

spec = app.openapi()

with open("openapi.json", "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

with open("openapi.yaml", "w", encoding="utf-8") as f:
    yaml.safe_dump(spec, f, allow_unicode=True, sort_keys=False)

operations = [(m.upper(), p) for p, methods in spec["paths"].items() for m in methods]
print(f"OpenAPI {spec['openapi']}: {len(operations)} операций, "
      f"методы: {sorted({m for m, _ in operations})}")
