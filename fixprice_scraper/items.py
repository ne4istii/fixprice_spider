from scrapy import Field, Item


class Product(Item):
    timestamp = Field(serializer=int)
    RPC = Field()
    url = Field()
    title = Field()
    marketing_tags = Field()
    brand = Field()
    section = Field()
    price_data = Field()
    stock = Field()
    assets = Field()
    metadata = Field()
    variants = Field(serializer=int)


class PriceData(Item):
    current = Field()
    original = Field()
    sale_tag = Field()


class Stock(Item):
    in_stock = Field()
    count = Field()


class Assets(Item):
    main_image = Field()
    set_images = Field()
    view360 = Field()
    video = Field()
