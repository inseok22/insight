from fastapi import HTTPException
from app.core.config import get_settings
from app.core.product import product_config


def require_feature(feature: str):
    def check() -> None:
        if feature not in product_config(get_settings())["features"]:
            raise HTTPException(status_code=403, detail="이 납품 구성에서 비활성화된 기능입니다.")
    return check
