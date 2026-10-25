"""The fixed choices shown in dropdowns. The server also uses them to reject anything else."""

CATEGORY_LABELS = {  # stored value -> label shown to the user
    "top": "Tops",
    "bottom": "Bottoms",
    "outerwear": "Outerwear",
    "footwear": "Footwear",
    "accessory": "Accessories",
}
OCCASIONS = ["Casual", "Work", "Formal", "Party", "Ethnic"]
SEASONS = ["Summer", "Winter", "Monsoon", "All-season"]
STYLES = ["Casual", "Formal", "Minimalist", "Streetwear", "Classic", "Bohemian", "Athleisure", "Ethnic"]

# `family` groups colours into the "colour mood" choices on the Outfit Matcher page.
COLORS = [
    {"name": "Black", "hex": "#1F1F1F", "family": "Monochrome"},
    {"name": "White", "hex": "#FFFFFF", "family": "Monochrome"},
    {"name": "Grey", "hex": "#9CA3AF", "family": "Neutrals"},
    {"name": "Charcoal", "hex": "#374151", "family": "Neutrals"},
    {"name": "Beige", "hex": "#E8D8C3", "family": "Neutrals"},
    {"name": "Cream", "hex": "#F5EEDC", "family": "Neutrals"},
    {"name": "Navy", "hex": "#1E3A5F", "family": "Neutrals"},
    {"name": "Denim Blue", "hex": "#4A6FA5", "family": "Neutrals"},
    {"name": "Olive", "hex": "#6B7F3A", "family": "Earthy"},
    {"name": "Terracotta", "hex": "#C8674A", "family": "Earthy"},
    {"name": "Brown", "hex": "#7B4B2A", "family": "Earthy"},
    {"name": "Sage", "hex": "#A3B18A", "family": "Earthy"},
    {"name": "Maroon", "hex": "#7A1F2B", "family": "Bold"},
    {"name": "Red", "hex": "#E5484D", "family": "Bold"},
    {"name": "Pink", "hex": "#F4A6B8", "family": "Bold"},
    {"name": "Gold", "hex": "#D4A437", "family": "Bold"},
]
COLOR_MOODS = ["Neutrals", "Monochrome", "Earthy", "Bold"]

STYLE_NOTES = [
    "Neutrals are your quiet superpower — a cream top with charcoal trousers works for almost any weekday.",
    "Pieces you haven't worn in a month are free outfits. Try pairing one with a favourite you trust.",
    "One statement piece per look is plenty. Let the rest of the outfit stay calm around it.",
    "Rolled sleeves and a tucked hem turn a work shirt into a weekend shirt in ten seconds.",
]

# The "one week" rule: an outfit should not repeat within 7 days. EVERY piece follows it (tops, bottoms, jackets, shoes, accessories).
# It is one fixed rule for every user, used by the hanger scans (tags.py) and by the Outfit Matcher (outfits.py).
REPEAT_WINDOW_DAYS = 7
REPEAT_EXEMPT = ()  # categories allowed to repeat. Empty = nothing is exempt. To let shoes repeat, put "footwear" here.
