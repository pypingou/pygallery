import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_dummy_images(base_photos_dir="photos"):
    """
    Generates dummy image files in specified album directories,
    including nested subdirectories, to help test the photo gallery application.
    """
    print(f"Starting dummy image generation in '{base_photos_dir}'...")

    # Define album directories, including nested ones
    album_names = [
        "VacationPhotos",
        "Cityscapes",
        "Family/Summer2023",
        "Family/Vacation/Paris",
        "Work/Conferences/2024"
    ]

    # Define image sizes for variety
    image_sizes = [(800, 600), (1024, 768), (1280, 720), (640, 480)]
    image_colors = ["red", "blue", "green", "purple", "orange", "cyan", "gray", "brown"]
    text_colors = [(255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 100, 0), (0, 0, 0), (255, 255, 255), (0, 255, 0), (255, 255, 255)]

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
        # Create the full path for the album, including nested directories
        album_path = base_path / album_name
        album_path.mkdir(parents=True, exist_ok=True) # parents=True creates intermediate directories
        print(f"Creating album directory: {album_path}")

        # Generate a few photos for each album
        for i in range(3): # Generate 3 photos per album
            # Cycle through colors and text colors
            bg_color = image_colors[(i + album_names.index(album_name)) % len(image_colors)]
            txt_color = text_colors[(i + album_names.index(album_name)) % len(text_colors)]
            size = image_sizes[i % len(image_sizes)]
            img_type = "jpg" if (i + album_names.index(album_name)) % 2 == 0 else "png" # Alternate types

            img_filename = f"photo_{i + 1}.{img_type}"
            img_path = album_path / img_filename

            try:
                img = Image.new('RGB', size, color=bg_color)
                d = ImageDraw.Draw(img)
                # Show the full album path in the image text
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

