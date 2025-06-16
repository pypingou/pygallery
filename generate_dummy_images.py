import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_dummy_images(base_photos_dir="photos"):
    """
    Generates dummy image files in specified album directories
    to help test the photo gallery application.
    """
    print(f"Starting dummy image generation in '{base_photos_dir}'...")

    # Define album directories
    album_names = ["VacationPhotos", "Cityscapes"]

    # Define image sizes for variety
    image_sizes = [(800, 600), (1024, 768), (1280, 720), (640, 480)]
    image_colors = ["red", "blue", "green", "purple", "orange", "cyan"]
    text_colors = [(255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 100, 0), (0, 0, 0), (255, 255, 255)]

    # Attempt to load a default font or fall back
    try:
        # This path might vary on different systems
        # Common paths: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf (Linux)
        # C:/Windows/Fonts/arial.ttf (Windows)
        # /System/Library/Fonts/SFCompactText.ttf (macOS)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except IOError:
        print("Warning: Could not load 'DejaVuSans-Bold.ttf'. Using default PIL font.")
        font = ImageFont.load_default()

    base_path = Path(base_photos_dir)
    base_path.mkdir(parents=True, exist_ok=True) # Ensure the base photos directory exists

    for album_name in album_names:
        album_path = base_path / album_name
        album_path.mkdir(parents=True, exist_ok=True)
        print(f"Creating album directory: {album_path}")

        for i in range(len(image_sizes)):
            # Cycle through colors and text colors
            bg_color = image_colors[i % len(image_colors)]
            txt_color = text_colors[i % len(text_colors)]
            size = image_sizes[i % len(image_sizes)]
            img_type = "jpg" if i % 2 == 0 else "png" # Alternate between jpg and png

            img_filename = f"photo_{i + 1}.{img_type}"
            img_path = album_path / img_filename

            try:
                img = Image.new('RGB', size, color=bg_color)
                d = ImageDraw.Draw(img)
                text_content = f"Album: {album_name}\nPhoto {i + 1}\n{size[0]}x{size[1]}"
                text_width, text_height = d.textbbox((0,0), text_content, font=font)[2:] # Get text bounding box size
                x = (size[0] - text_width) / 2
                y = (size[1] - text_height) / 2
                d.text((x, y), text_content, font=font, fill=txt_color, align="center")
                img.save(img_path)
                print(f"  Generated {img_filename} in {album_name}")
            except Exception as e:
                print(f"Error generating {img_filename} for {album_name}: {e}")

    print("\nDummy image generation complete!")
    print(f"You can find the images in the '{base_photos_dir}' directory.")

if __name__ == "__main__":
    generate_dummy_images()

