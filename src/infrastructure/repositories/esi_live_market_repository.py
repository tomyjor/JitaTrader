from collections import defaultdict
from typing import List

import requests

from models.market_item import MarketItem
from repositories.type_repository import TypeRepository


class ESIMarketRepository:

    BASE_URL = "https://esi.evetech.net/latest"

    def __init__(self, timeout: int = 30):

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": "JitaTrader/1.0"
            }
        )

        self.type_repository = TypeRepository()

    def load_region(
        self,
        region_id: int,
        region_name: str,
    ) -> List[MarketItem]:

        orders = self._download_orders(region_id)

        return self._build_market_items(
            orders,
            region_name,
        )

    def _download_orders(self, region_id: int):

        url = f"{self.BASE_URL}/markets/{region_id}/orders/"

        response = self.session.get(
            url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        pages = int(
            response.headers.get(
                "X-Pages",
                1,
            )
        )

        orders = response.json()

        for page in range(2, pages + 1):

            response = self.session.get(
                url,
                params={"page": page},
                timeout=self.timeout,
            )

            response.raise_for_status()

            orders.extend(
                response.json()
            )

        return orders

    def _build_market_items(
        self,
        orders,
        region_name: str,
    ) -> List[MarketItem]:

        grouped = defaultdict(
            lambda: {
                "buy": [],
                "sell": [],
            }
        )

        for order in orders:

            grouped[
                order["type_id"]
            ][
                "buy" if order["is_buy_order"] else "sell"
            ].append(order)

        items = []

        for type_id, market in grouped.items():

            if not market["buy"] or not market["sell"]:
                continue

            info = self.type_repository.get(type_id)

            if info is None:
                continue

            best_buy = max(
                market["buy"],
                key=lambda x: x["price"],
            )

            best_sell = min(
                market["sell"],
                key=lambda x: x["price"],
            )

            buy_volume = sum(
                o["volume_remain"]
                for o in market["buy"]
            )

            sell_volume = sum(
                o["volume_remain"]
                for o in market["sell"]
            )

            items.append(

                MarketItem(

                    type_id=type_id,

                    type_name=info["name"],

                    buy_price=best_buy["price"],

                    sell_price=best_sell["price"],

                    volume=min(
                        buy_volume,
                        sell_volume,
                    ),

                    group=str(info["group_id"]),

                    category=str(info["category_id"]),

                    region=region_name,

                    packaged_volume=info["volume"],

                    adjusted_price=info["base_price"],

                    average_price=0,

                )

            )

        return items

    def close(self):

        self.session.close()