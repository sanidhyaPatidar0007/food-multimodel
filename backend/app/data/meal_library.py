"""Built-in meal library for the planner (hand-written, approximate per-serving values).

`diet` = the strictest diet the meal fits (a vegan meal suits everyone).
`allergens` is declared by hand; the planner ALSO derives allergens from ingredient names and
uses the union, and tests check that the derived set is a subset of the declared one.
Nutrition per serving is an ESTIMATE (rounded) -- not computed from lab data.
Format of ingredients: "name:qty:unit;..." ; steps: "step|step".
"""
from __future__ import annotations

# slot, id, name, diet, allergens, cuisine, prep_min, cost(1-3), kcal, protein, carbs, fat, ingredients, steps
_M = [
    ("breakfast", "b-oats-banana", "Oats with banana and chia", "vegan", ["gluten"], "international", 5, 1, 350, 12, 58, 8,
     "rolled oats:50:g;banana:1:whole;chia seeds:1:tbsp;water:200:ml;cinnamon:0.5:tsp", "Simmer oats in water for 5 minutes.|Top with sliced banana, chia and cinnamon."),
    ("breakfast", "b-yogurt-fruit", "Yogurt parfait with fruit", "vegetarian", ["milk"], "international", 5, 2, 320, 20, 38, 9,
     "plain yogurt:200:g;mixed berries:100:g;banana:0.5:whole;honey:1:tsp", "Layer yogurt and fruit in a glass.|Drizzle with honey."),
    ("breakfast", "b-veg-omelette", "Vegetable omelette with toast", "vegetarian", ["egg", "gluten"], "international", 12, 1, 400, 24, 28, 21,
     "eggs:2:whole;spinach:40:g;tomato:0.5:whole;whole wheat bread:2:slice;oil:1:tsp", "Whisk eggs and pour into an oiled pan.|Add chopped vegetables, cook until fully set.|Serve with toast."),
    ("breakfast", "b-tofu-scramble", "Tofu scramble with spinach", "vegan", ["soy"], "international", 12, 2, 330, 24, 14, 20,
     "firm tofu:200:g;spinach:60:g;onion:0.5:whole;turmeric:0.5:tsp;oil:1:tsp", "Crumble tofu into an oiled pan with chopped onion.|Add turmeric and spinach; cook 6-8 minutes."),
    ("breakfast", "b-pb-toast", "Peanut butter banana toast", "vegan", ["peanut", "gluten"], "international", 5, 1, 380, 13, 50, 15,
     "whole wheat bread:2:slice;peanut butter:2:tbsp;banana:1:whole", "Toast the bread.|Spread peanut butter and top with banana slices."),
    ("breakfast", "b-poha", "Vegetable poha", "vegan", [], "indian", 15, 1, 300, 6, 54, 7,
     "flattened rice (poha):60:g;green peas:50:g;onion:0.5:whole;turmeric:0.5:tsp;oil:1:tsp;lemon:0.5:whole;coriander leaves:1:tbsp",
     "Rinse poha and drain.|Saute onion and peas with turmeric in oil.|Add poha, heat through, finish with lemon and coriander."),
    ("breakfast", "b-salmon-toast", "Smoked salmon and avocado toast", "pescatarian", ["fish", "gluten"], "international", 8, 3, 420, 22, 32, 22,
     "whole wheat bread:2:slice;smoked salmon:60:g;avocado:0.5:whole;lemon:0.25:whole", "Toast bread and mash avocado on top.|Add salmon and a squeeze of lemon."),

    ("lunch", "l-chickpea-bowl", "Chickpea and vegetable salad bowl", "vegan", [], "mediterranean", 15, 1, 450, 17, 58, 17,
     "chickpeas (cooked):150:g;cucumber:0.5:whole;tomato:1:whole;red onion:0.25:whole;olive oil:1:tbsp;lemon:0.5:whole;parsley:2:tbsp",
     "Combine chickpeas and chopped vegetables.|Dress with olive oil, lemon and parsley."),
    ("lunch", "l-dal-rice", "Lentil dal with rice", "vegan", [], "indian", 30, 1, 520, 22, 84, 10,
     "red lentils:80:g;white rice (raw):60:g;onion:0.5:whole;tomato:1:whole;turmeric:0.5:tsp;cumin seeds:0.5:tsp;oil:2:tsp",
     "Boil lentils with turmeric until soft, about 20 minutes.|Fry cumin, onion and tomato; stir into the dal.|Serve with steamed rice."),
    ("lunch", "l-paneer-wrap", "Paneer tikka wrap", "vegetarian", ["milk", "gluten"], "indian", 20, 2, 560, 26, 52, 26,
     "paneer:100:g;whole wheat tortilla:1:whole;bell pepper:0.5:whole;onion:0.25:whole;yogurt:2:tbsp;tikka spice mix:1:tsp",
     "Marinate paneer in yogurt and spices.|Pan-sear with pepper and onion.|Roll in the tortilla."),
    ("lunch", "l-chicken-quinoa", "Grilled chicken quinoa bowl", "omnivore", [], "international", 25, 2, 540, 42, 52, 16,
     "chicken breast:130:g;quinoa (raw):60:g;broccoli:100:g;olive oil:1:tsp;lemon:0.5:whole",
     "Cook quinoa.|Grill or pan-cook chicken until it reaches 74 C / 165 F inside.|Steam broccoli and assemble the bowl."),
    ("lunch", "l-tofu-stirfry", "Tofu and vegetable stir-fry with rice", "vegan", ["soy"], "asian", 20, 2, 480, 22, 62, 14,
     "firm tofu:120:g;broccoli:100:g;carrot:1:whole;white rice (raw):60:g;soy sauce:1:tbsp;oil:1:tsp;garlic:2:clove",
     "Cook rice.|Pan-fry tofu cubes until golden.|Stir-fry vegetables and garlic, add soy sauce, combine."),
    ("lunch", "l-tuna-sandwich", "Tuna salad sandwich", "pescatarian", ["fish", "egg", "gluten"], "international", 8, 2, 470, 30, 42, 18,
     "canned tuna:90:g;whole wheat bread:2:slice;mayonnaise:1:tbsp;celery:1:stalk;lettuce:20:g", "Mix tuna, mayonnaise and chopped celery.|Fill the sandwich with lettuce and tuna."),
    ("lunch", "l-rajma-rice", "Rajma (kidney bean curry) with brown rice", "vegan", [], "indian", 40, 1, 500, 20, 80, 9,
     "kidney beans (cooked):150:g;brown rice (raw):60:g;onion:0.5:whole;tomato:2:whole;ginger:1:tsp;garam masala:1:tsp;oil:2:tsp",
     "Fry onion, ginger and tomato into a masala.|Add cooked beans and spices; simmer 15 minutes.|Serve with brown rice."),
    ("lunch", "l-shrimp-bowl", "Shrimp and vegetable rice bowl", "pescatarian", ["shellfish", "soy"], "asian", 20, 3, 480, 32, 60, 10,
     "shrimp:130:g;white rice (raw):60:g;bell pepper:0.5:whole;snap peas:80:g;soy sauce:1:tbsp;garlic:2:clove;oil:1:tsp",
     "Cook rice.|Saute garlic and vegetables, then add shrimp until pink and opaque.|Season with soy sauce and serve over rice."),

    ("dinner", "d-salmon-sweetpotato", "Baked salmon with sweet potato and broccoli", "pescatarian", ["fish"], "international", 30, 3, 560, 38, 48, 24,
     "salmon fillet:150:g;sweet potato:200:g;broccoli:120:g;olive oil:1:tsp;lemon:0.5:whole", "Roast sweet potato wedges 20 minutes at 200 C.|Add salmon for the last 12 minutes; cook until flaky (63 C / 145 F).|Steam broccoli."),
    ("dinner", "d-chicken-curry", "Chicken curry with rice", "omnivore", [], "indian", 40, 2, 600, 40, 62, 20,
     "chicken thigh (boneless):150:g;white rice (raw):65:g;onion:1:whole;tomato:2:whole;ginger garlic paste:1:tbsp;curry spices:2:tsp;oil:2:tsp",
     "Fry onion, paste and spices; add tomato.|Add chicken and simmer 20 minutes until cooked through (74 C / 165 F).|Serve with rice."),
    ("dinner", "d-chana-masala", "Chana masala with roti", "vegan", ["gluten"], "indian", 35, 1, 540, 20, 82, 14,
     "chickpeas (cooked):180:g;whole wheat flour (for roti):60:g;onion:1:whole;tomato:2:whole;chana masala spice:2:tsp;oil:2:tsp",
     "Fry onion, tomato and spices into a thick masala.|Simmer chickpeas in it for 15 minutes.|Serve with fresh roti."),
    ("dinner", "d-pasta-primavera", "Vegetable pasta primavera", "vegan", ["gluten"], "italian", 25, 1, 520, 18, 86, 12,
     "pasta:90:g;zucchini:1:whole;cherry tomatoes:100:g;garlic:2:clove;olive oil:1:tbsp;basil:5:g", "Boil pasta.|Saute garlic and vegetables in oil.|Toss with pasta and basil."),
    ("dinner", "d-tofu-noodles", "Tofu and broccoli stir-fry noodles", "vegan", ["soy", "gluten", "sesame"], "asian", 20, 2, 540, 26, 70, 16,
     "firm tofu:120:g;wheat noodles:90:g;broccoli:100:g;carrot:1:whole;soy sauce:1:tbsp;sesame oil:1:tsp",
     "Cook noodles.|Fry tofu, add vegetables and sauce.|Toss with noodles and sesame oil."),
    ("dinner", "d-khichdi", "Vegetable khichdi", "vegan", [], "indian", 30, 1, 450, 16, 78, 8,
     "rice (raw):50:g;yellow moong dal:40:g;mixed vegetables:120:g;cumin seeds:0.5:tsp;turmeric:0.5:tsp;oil:2:tsp",
     "Rinse rice and dal.|Fry cumin, add vegetables, rice, dal, turmeric and water.|Simmer until soft and porridge-like."),
    ("dinner", "d-egg-curry", "Egg curry with rice", "vegetarian", ["egg"], "indian", 30, 1, 560, 26, 68, 20,
     "eggs:3:whole;white rice (raw):65:g;onion:1:whole;tomato:2:whole;curry spices:2:tsp;oil:2:tsp",
     "Hard-boil the eggs.|Cook onion, tomato and spices into a gravy.|Add peeled eggs and simmer 8 minutes; serve with rice."),
    ("dinner", "d-beef-stirfry", "Lean beef and vegetable stir-fry with rice", "omnivore", ["soy"], "asian", 25, 3, 600, 40, 60, 20,
     "lean beef strips:130:g;white rice (raw):60:g;bell pepper:1:whole;broccoli:100:g;soy sauce:1:tbsp;oil:1:tsp",
     "Cook rice.|Stir-fry beef in a hot pan until browned and cooked through.|Add vegetables and sauce."),

    ("snack", "s-apple-pb", "Apple with peanut butter", "vegan", ["peanut"], "international", 3, 1, 200, 5, 26, 9, "apple:1:whole;peanut butter:1:tbsp", "Slice the apple and serve with peanut butter."),
    ("snack", "s-roast-chickpeas", "Roasted chickpeas", "vegan", [], "international", 30, 1, 150, 7, 22, 4, "chickpeas (cooked):100:g;olive oil:0.5:tsp;paprika:0.5:tsp", "Dry the chickpeas, toss with oil and spice.|Roast at 200 C for 25 minutes."),
    ("snack", "s-yogurt-berries", "Yogurt with berries", "vegetarian", ["milk"], "international", 2, 1, 140, 10, 17, 3, "plain yogurt:150:g;mixed berries:60:g", "Combine and serve."),
    ("snack", "s-mixed-nuts", "Handful of almonds and walnuts", "vegan", ["tree_nut"], "international", 1, 2, 180, 6, 7, 16, "almonds:15:g;walnuts:15:g", "Serve a small handful."),
    ("snack", "s-fruit-bowl", "Seasonal fruit bowl", "vegan", [], "international", 5, 1, 120, 1.5, 30, 0.5, "seasonal fruit:200:g", "Chop and serve."),
    ("snack", "s-hummus-carrot", "Hummus with carrot sticks", "vegan", ["sesame"], "mediterranean", 5, 1, 170, 6, 20, 8, "hummus:50:g;carrot:2:whole", "Cut carrots into sticks and serve with hummus."),
    ("snack", "s-egg-cucumber", "Boiled egg with cucumber", "vegetarian", ["egg"], "international", 12, 1, 120, 9, 3, 8, "eggs:1.5:whole;cucumber:0.5:whole", "Boil eggs 9-10 minutes, peel, and serve with cucumber."),
    ("snack", "s-makhana", "Roasted makhana (fox nuts)", "vegan", [], "indian", 8, 1, 110, 4, 20, 2, "makhana:30:g;oil:0.5:tsp;salt:1:pinch", "Roast makhana with a little oil until crisp."),
]


def _parse_ings(s: str) -> list[dict]:
    out = []
    for part in s.split(";"):
        name, qty, unit = part.rsplit(":", 2)
        out.append({"name": name.strip(), "quantity": float(qty), "unit": unit.strip()})
    return out


def load_meals() -> list[dict]:
    keys = ("slot", "id", "name", "diet", "allergens", "cuisine", "prep_minutes", "cost", "kcal", "protein_g", "carbs_g", "fat_g")
    meals = []
    for row in _M:
        m = dict(zip(keys, row[:12]))
        m["ingredients"] = _parse_ings(row[12])
        m["steps"] = row[13].split("|")
        meals.append(m)
    return meals
