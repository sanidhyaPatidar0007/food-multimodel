"""Bundled nutrition reference table (per 100 g, edible portion).

PROVENANCE / LIMITS
  Rounded, approximate typical values compiled for this demo. They are NOT a verified
  lab dataset. Real dishes vary widely with recipe, brand and preparation.
  For production, import USDA FoodData Central (or a national equivalent) into this
  schema -- see README "Adding datasets".

Columns: key, name, aliases, category, kcal, protein, carbs, fat, fiber, sugar, sat_fat,
         sodium_mg, serving_g, serving_desc, tags, alternatives
Tags drive the health-score logic: whole, fried, processed, dessert, lean_protein.
"""
from __future__ import annotations

DATASET_NAME = "FoodVerse bundled reference (approximate, rounded; not a verified dataset)"

_ROWS = [
    # key, name, aliases, category, kcal, P, C, F, fiber, sugar, satF, Na, serving_g, serving_desc, tags, alternatives
    ("apple", "Apple", ["apples"], "fruit", 52, 0.3, 13.8, 0.2, 2.4, 10.4, 0.0, 1, 180, "1 medium", ["whole"], []),
    ("banana", "Banana", ["bananas"], "fruit", 89, 1.1, 22.8, 0.3, 2.6, 12.2, 0.1, 1, 118, "1 medium", ["whole"], []),
    ("orange", "Orange", ["oranges"], "fruit", 47, 0.9, 11.8, 0.1, 2.4, 9.4, 0.0, 0, 130, "1 medium", ["whole"], []),
    ("strawberry", "Strawberries", ["strawberries"], "fruit", 32, 0.7, 7.7, 0.3, 2.0, 4.9, 0.0, 1, 150, "1 cup", ["whole"], []),
    ("grapes", "Grapes", ["grape"], "fruit", 69, 0.7, 18.1, 0.2, 0.9, 15.5, 0.1, 2, 150, "1 cup", ["whole"], []),
    ("watermelon", "Watermelon", [], "fruit", 30, 0.6, 7.6, 0.2, 0.4, 6.2, 0.0, 1, 280, "1 wedge", ["whole"], []),
    ("avocado", "Avocado", ["guacamole"], "fruit", 160, 2.0, 8.5, 14.7, 6.7, 0.7, 2.1, 7, 100, "half", ["whole"], []),
    ("broccoli", "Broccoli", [], "vegetable", 34, 2.8, 6.6, 0.4, 2.6, 1.7, 0.1, 33, 90, "1 cup", ["whole"], []),
    ("carrot", "Carrots", ["carrot"], "vegetable", 41, 0.9, 9.6, 0.2, 2.8, 4.7, 0.0, 69, 80, "1 medium", ["whole"], []),
    ("tomato", "Tomato", ["tomatoes"], "vegetable", 18, 0.9, 3.9, 0.2, 1.2, 2.6, 0.0, 5, 120, "1 medium", ["whole"], []),
    ("spinach", "Spinach", [], "vegetable", 23, 2.9, 3.6, 0.4, 2.2, 0.4, 0.1, 79, 60, "2 cups raw", ["whole"], []),
    ("cucumber", "Cucumber", [], "vegetable", 15, 0.7, 3.6, 0.1, 0.5, 1.7, 0.0, 2, 100, "1/2 cucumber", ["whole"], []),
    ("potato", "Boiled potato", ["potatoes", "boiled potato", "mashed potato"], "vegetable", 87, 1.9, 20.1, 0.1, 1.8, 0.9, 0.0, 5, 170, "1 medium", ["whole"], []),
    ("salad", "Mixed green salad", ["green salad", "garden salad", "mixed salad"], "vegetable", 20, 1.4, 3.5, 0.2, 2.0, 1.5, 0.0, 20, 150, "1 bowl (undressed)", ["whole"], []),
    ("caesar_salad", "Caesar salad", ["caesar"], "mixed", 190, 6.0, 8.0, 15.0, 1.5, 1.5, 3.0, 420, 200, "1 bowl", ["processed"], ["salad"]),
    ("white_rice", "White rice (cooked)", ["rice", "steamed rice"], "grain", 130, 2.7, 28.2, 0.3, 0.4, 0.1, 0.1, 1, 160, "1 cup", [], ["brown_rice"]),
    ("brown_rice", "Brown rice (cooked)", [], "grain", 112, 2.3, 23.5, 0.8, 1.8, 0.4, 0.2, 5, 160, "1 cup", ["whole"], []),
    ("fried_rice", "Fried rice", [], "mixed", 163, 4.0, 24.0, 5.5, 1.0, 1.5, 1.0, 400, 200, "1 cup", ["fried"], ["brown_rice"]),
    ("pasta", "Pasta (cooked)", ["spaghetti", "noodles", "macaroni"], "grain", 158, 5.8, 30.9, 0.9, 1.8, 0.6, 0.2, 1, 200, "1 cup", [], ["salad"]),
    ("bread", "White bread", ["toast", "sandwich bread"], "grain", 265, 9.0, 49.0, 3.2, 2.7, 5.0, 0.7, 491, 60, "2 slices", ["processed"], ["oatmeal"]),
    ("oatmeal", "Oatmeal (cooked)", ["porridge", "oats"], "grain", 71, 2.5, 12.0, 1.5, 1.7, 0.3, 0.3, 4, 240, "1 cup", ["whole"], []),
    ("pancakes", "Pancakes", ["pancake"], "grain", 227, 6.4, 28.0, 10.0, 1.2, 6.0, 2.0, 430, 150, "3 medium", ["processed"], ["oatmeal"]),
    ("pizza", "Cheese pizza", ["pizza slice"], "mixed", 266, 11.0, 33.0, 10.0, 2.3, 3.6, 4.5, 598, 107, "1 slice", ["processed"], ["salad"]),
    ("hamburger", "Hamburger", ["burger", "cheeseburger"], "mixed", 250, 12.5, 29.0, 9.5, 1.5, 5.0, 3.5, 500, 200, "1 burger", ["processed"], ["grilled_chicken", "salad"]),
    ("french_fries", "French fries", ["fries", "chips"], "mixed", 312, 3.4, 41.0, 15.0, 3.8, 0.3, 2.5, 210, 117, "1 medium", ["fried"], ["potato"]),
    ("fried_chicken", "Fried chicken", [], "protein", 260, 19.0, 10.0, 16.0, 0.5, 0.0, 4.0, 450, 150, "2 pieces", ["fried"], ["grilled_chicken"]),
    ("grilled_chicken", "Grilled chicken breast", ["chicken breast", "chicken"], "protein", 165, 31.0, 0.0, 3.6, 0.0, 0.0, 1.0, 74, 120, "1 breast", ["lean_protein"], []),
    ("beef_steak", "Beef steak (cooked)", ["steak", "beef"], "protein", 271, 25.0, 0.0, 19.0, 0.0, 0.0, 7.5, 60, 150, "1 steak", [], ["grilled_chicken"]),
    ("salmon", "Salmon (cooked)", ["grilled salmon", "fish"], "protein", 206, 22.0, 0.0, 12.0, 0.0, 0.0, 2.5, 61, 150, "1 fillet", ["lean_protein"], []),
    ("egg", "Boiled egg", ["eggs", "boiled eggs"], "protein", 155, 12.6, 1.1, 10.6, 0.0, 1.1, 3.3, 124, 100, "2 eggs", [], []),
    ("omelette", "Omelette", ["omelet", "scrambled eggs"], "protein", 154, 10.6, 0.6, 11.7, 0.0, 0.5, 3.5, 155, 120, "2-egg omelette", [], []),
    ("tofu", "Tofu", ["bean curd"], "protein", 76, 8.0, 1.9, 4.8, 0.3, 0.6, 0.7, 7, 120, "1/2 cup", ["lean_protein"], []),
    ("lentils", "Lentils (cooked)", ["dal", "dahl", "lentil soup"], "legume", 116, 9.0, 20.0, 0.4, 7.9, 1.8, 0.1, 2, 200, "1 cup", ["whole"], []),
    ("chickpeas", "Chickpeas (cooked)", ["hummus", "chana"], "legume", 164, 8.9, 27.4, 2.6, 7.6, 4.8, 0.3, 7, 160, "1 cup", ["whole"], []),
    ("yogurt", "Plain yogurt", ["yoghurt", "curd"], "dairy", 61, 3.5, 4.7, 3.3, 0.0, 4.7, 2.1, 46, 245, "1 cup", [], []),
    ("cheese", "Cheddar cheese", ["cheddar"], "dairy", 403, 25.0, 1.3, 33.0, 0.0, 0.5, 21.0, 653, 30, "1 slice", [], []),
    ("sushi", "Sushi roll", ["maki", "sushi roll"], "mixed", 150, 5.0, 28.0, 1.0, 0.8, 4.0, 0.2, 380, 180, "6 pieces", [], []),
    ("tacos", "Beef taco", ["taco"], "mixed", 226, 9.0, 20.0, 12.0, 3.0, 1.5, 4.5, 400, 100, "1 taco", ["processed"], ["salad"]),
    ("curry", "Chicken curry", ["chicken curry", "butter chicken"], "mixed", 150, 10.0, 6.0, 9.0, 1.2, 3.0, 3.0, 380, 250, "1 cup", [], ["lentils"]),
    ("ice_cream", "Ice cream", ["gelato"], "dessert", 207, 3.5, 24.0, 11.0, 0.7, 21.0, 6.8, 80, 100, "1/2 cup", ["dessert"], ["yogurt", "strawberry"]),
    ("chocolate_cake", "Chocolate cake", ["cake"], "dessert", 371, 5.0, 53.0, 16.0, 1.4, 36.0, 4.5, 370, 100, "1 slice", ["dessert"], ["strawberry"]),
    ("donut", "Donut", ["doughnut"], "dessert", 421, 4.9, 51.0, 25.0, 1.7, 22.0, 10.0, 326, 60, "1 donut", ["dessert", "fried"], ["oatmeal", "banana"]),
    ("apple_pie", "Apple pie", [], "dessert", 237, 1.9, 34.0, 11.0, 1.6, 15.0, 4.5, 266, 125, "1 slice", ["dessert"], ["apple"]),
    ("waffles", "Waffles", ["waffle"], "grain", 291, 7.9, 33.0, 14.0, 1.4, 6.5, 3.5, 511, 75, "1 waffle", ["processed"], ["oatmeal"]),
    ("hot_dog", "Hot dog with bun", ["hotdog", "hot dogs"], "mixed", 250, 10.0, 22.0, 14.0, 1.0, 4.0, 5.0, 700, 100, "1 hot dog", ["processed"], ["grilled_chicken"]),
    ("lasagna", "Lasagna", [], "mixed", 150, 8.0, 14.0, 6.0, 1.2, 3.0, 3.0, 350, 250, "1 piece", [], ["salad"]),
    ("mac_and_cheese", "Macaroni and cheese", ["macaroni and cheese", "mac and cheese"], "mixed", 164, 6.5, 20.0, 6.5, 0.9, 3.0, 3.0, 450, 200, "1 cup", ["processed"], ["pasta"]),
    ("cheesecake", "Cheesecake", [], "dessert", 321, 5.5, 26.0, 23.0, 0.4, 22.0, 13.0, 270, 100, "1 slice", ["dessert"], ["strawberry"]),
    ("spaghetti_bolognese", "Spaghetti bolognese", ["bolognese"], "mixed", 140, 7.0, 16.0, 5.0, 1.5, 3.0, 1.8, 300, 300, "1 plate", [], ["salad"]),
    ("chicken_wings", "Chicken wings", ["wings", "buffalo wings"], "protein", 290, 27.0, 0.0, 20.0, 0.0, 0.0, 5.5, 420, 120, "4 wings", ["fried"], ["grilled_chicken"]),
    ("dumplings", "Dumplings", ["gyoza", "dumpling", "momos"], "mixed", 200, 8.0, 26.0, 7.0, 1.2, 1.5, 2.0, 400, 150, "5 pieces", [], ["salad"]),
    ("ramen", "Ramen (noodle soup)", ["noodle soup", "pho"], "mixed", 80, 4.0, 10.0, 2.5, 0.5, 0.8, 1.0, 400, 450, "1 bowl", ["processed"], ["salad"]),
    ("greek_salad", "Greek salad", [], "vegetable", 110, 3.0, 5.0, 9.0, 1.5, 3.0, 3.5, 320, 200, "1 bowl", [], []),
]


def load_rows() -> list[dict]:
    keys = ["key", "name", "aliases", "category", "kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
            "sugar_g", "sat_fat_g", "sodium_mg", "serving_g", "serving_desc", "tags", "alternatives"]
    return [dict(zip(keys, r)) for r in _ROWS]
