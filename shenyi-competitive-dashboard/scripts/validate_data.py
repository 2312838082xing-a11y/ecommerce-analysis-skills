#!/usr/bin/env python3
"""验证生意参谋 Dashboard 中间 JSON 的核心数据契约。"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


STORE_METRICS = ("visitors", "buyers", "conv_rate", "cart_adds", "favorites")
LINK_FIELDS = (
    "product_name", "product_id", "dates", "visitors", "buyers", "conv_rate",
    "cart_adds", "favorites", "total_buyers_mid", "keywords", "skus", "traffic",
)


def validate_range(value: Any, path: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{path}: 应为区间对象或 null，实际为 {type(value).__name__}")
        return
    missing = [key for key in ("low", "mid", "high") if key not in value]
    if missing:
        errors.append(f"{path}: 缺少 {missing}")
        return
    numbers = [value[key] for key in ("low", "mid", "high")]
    if any(isinstance(number, bool) or not isinstance(number, (int, float)) for number in numbers):
        errors.append(f"{path}: low/mid/high 必须是数值")
        return
    if any(not math.isfinite(number) for number in numbers):
        errors.append(f"{path}: 含非有限数值")
    if not numbers[0] <= numbers[1] <= numbers[2]:
        errors.append(f"{path}: 必须满足 low <= mid <= high")
    if value.get("exact") is True and not numbers[0] == numbers[1] == numbers[2]:
        errors.append(f"{path}: exact=true 但三值不相等")


def validate_series(entity: dict[str, Any], path: str, errors: list[str]) -> None:
    dates = entity.get("dates")
    if not isinstance(dates, list):
        errors.append(f"{path}.dates: 必须是数组")
        return
    if not all(isinstance(period, str) and period for period in dates):
        errors.append(f"{path}.dates: 每个日期键必须是非空字符串")
    if len(dates) != len(set(dates)):
        errors.append(f"{path}.dates: 存在重复日期")
    for metric in STORE_METRICS:
        values = entity.get(metric)
        if not isinstance(values, list):
            errors.append(f"{path}.{metric}: 必须是数组")
            continue
        if len(values) != len(dates):
            errors.append(f"{path}.{metric}: 长度 {len(values)} 与 dates {len(dates)} 不一致")
        for index, value in enumerate(values):
            validate_range(value, f"{path}.{metric}[{index}]", errors)


def validate_document(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["根节点必须是对象"]

    store = document.get("store")
    product = document.get("product")
    if not isinstance(store, dict):
        errors.append("store: 必须是对象")
    else:
        stores = store.get("stores")
        data = store.get("data")
        if not isinstance(stores, list) or not all(isinstance(name, str) for name in stores):
            errors.append("store.stores: 必须是字符串数组")
            stores = []
        if not isinstance(data, dict):
            errors.append("store.data: 必须是对象")
            data = {}
        if set(stores) != set(data):
            errors.append("store.stores 与 store.data 的键不一致")
        for name, entity in data.items():
            if not isinstance(entity, dict):
                errors.append(f"store.data[{name!r}]: 必须是对象")
                continue
            if "category" not in entity:
                errors.append(f"store.data[{name!r}]: 缺少 category")
            validate_series(entity, f"store.data[{name!r}]", errors)
        global_dates = store.get("dates")
        expected_dates = sorted({date for entity in data.values() if isinstance(entity, dict)
                                 for date in entity.get("dates", []) if isinstance(date, str)})
        if not isinstance(global_dates, list):
            errors.append("store.dates: 必须是数组")
        elif global_dates != expected_dates:
            errors.append("store.dates 必须等于所有店铺日期的排序并集")

    if not isinstance(product, dict):
        errors.append("product: 必须是对象")
    else:
        competitors = product.get("competitors")
        data = product.get("data")
        if not isinstance(competitors, list) or not all(isinstance(name, str) for name in competitors):
            errors.append("product.competitors: 必须是字符串数组")
            competitors = []
        if not isinstance(data, dict):
            errors.append("product.data: 必须是对象")
            data = {}
        if set(competitors) != set(data):
            errors.append("product.competitors 与 product.data 的键不一致")
        for name, competitor in data.items():
            path = f"product.data[{name!r}]"
            if not isinstance(competitor, dict):
                errors.append(f"{path}: 必须是对象")
                continue
            for field in ("price", "price_note", "price_tier", "all_link_ids", "links"):
                if field not in competitor:
                    errors.append(f"{path}: 缺少 {field}")
            price = competitor.get("price")
            if price is not None and (
                isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price)
            ):
                errors.append(f"{path}.price: 必须是有限数值或 null")
            if not isinstance(competitor.get("price_note"), str):
                errors.append(f"{path}.price_note: 必须是字符串")
            if not isinstance(competitor.get("price_tier"), str):
                errors.append(f"{path}.price_tier: 必须是字符串")
            ids = competitor.get("all_link_ids", [])
            if isinstance(ids, list):
                for index, product_id in enumerate(ids):
                    if not isinstance(product_id, str) or not re.fullmatch(r"\d+", product_id):
                        errors.append(f"{path}.all_link_ids[{index}]: 必须是纯数字字符串")
            links = competitor.get("links", [])
            if not isinstance(links, list):
                errors.append(f"{path}.links: 必须是数组")
                continue
            link_ids: set[str] = set()
            for index, link in enumerate(links):
                link_path = f"{path}.links[{index}]"
                if not isinstance(link, dict):
                    errors.append(f"{link_path}: 必须是对象")
                    continue
                for field in LINK_FIELDS:
                    if field not in link:
                        errors.append(f"{link_path}: 缺少 {field}")
                product_id = link.get("product_id")
                if not isinstance(product_id, str) or not re.fullmatch(r"\d+", product_id):
                    errors.append(f"{link_path}.product_id: 必须是纯数字字符串")
                elif product_id in link_ids:
                    errors.append(f"{path}: 商品 ID {product_id} 重复")
                else:
                    link_ids.add(product_id)
                validate_series(link, link_path, errors)
                total_buyers = link.get("total_buyers_mid")
                if (
                    isinstance(total_buyers, bool)
                    or not isinstance(total_buyers, (int, float))
                    or not math.isfinite(total_buyers)
                ):
                    errors.append(f"{link_path}.total_buyers_mid: 必须是有限数值")
            if isinstance(ids, list) and set(ids) != link_ids:
                errors.append(f"{path}.all_link_ids 与 links 中的 product_id 不一致")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", help="待验证的 JSON 文件")
    args = parser.parse_args()
    path = Path(args.json_file)
    document = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_document(document)
    if errors:
        print(f"validation failed: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("validation passed")


if __name__ == "__main__":
    main()
