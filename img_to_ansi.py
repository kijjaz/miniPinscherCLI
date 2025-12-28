from PIL import Image
import sys

# Character set for density (not used in block mode, but good for fallback)
CHARS = [" ", "░", "▒", "▓", "█"]

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def image_to_rich_ansi(image_path, width=60):
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Error opening image: {e}")
        return ""

    # Calculate height to preserve aspect ratio (terminal characters are roughly 2x tall)
    w_percent = (width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)) * 0.5)
    
    img = img.resize((width, h_size), Image.Resampling.NEAREST)
    img = img.convert("RGBA")
    
    ascii_str = ""
    width, height = img.size
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = img.getpixel((x, y))
            r, g, b, a = img.getpixel((x, y))
            # Treat transparency OR near-black as space to isolate the sprite
            if a < 128 or (r < 20 and g < 20 and b < 20):
                ascii_str += " " # Transparent/Black background
            else:
                color = rgb_to_hex(r, g, b)
                # Using upper half block or full block?
                # Rich markup: [color]█[/color]
                ascii_str += f"[{color}]█[/{color}]"
        ascii_str += "\\n"
    
    return ascii_str

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python img_to_ansi.py <image_path>")
        sys.exit(1)
        
    width = 60
    if len(sys.argv) > 2:
        width = int(sys.argv[2])
    art = image_to_rich_ansi(sys.argv[1], width=width)
    # Print raw string for copying (escaping backslashes for python string literal)
    print(art)
