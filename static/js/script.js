// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
    // Determine if we are on the main gallery page or an album page
    const pathname = window.location.pathname;
    if (pathname === '/') {
        fetchAlbums();
    } else if (pathname.startsWith('/album/')) {
        const albumName = pathname.split('/album/')[1];
        if (albumName) {
            document.getElementById('album-title').textContent = `Album: ${decodeURIComponent(albumName)}`;
            fetchPhotos(albumName);
        }
    }

    // Lightbox functionality
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const closeBtn = document.querySelector('.close-btn');

    closeBtn.addEventListener('click', (event) => {
        event.stopPropagation(); // Prevent click from bubbling to lightbox overlay
        closeLightbox();
    });

    // Close lightbox when clicking outside the image
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    // Close lightbox with ESC key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && lightbox.classList.contains('active')) {
            closeLightbox();
        }
    });

    // Attach openLightbox to global scope for easy access from dynamically created elements
    window.openLightbox = (imageUrl) => {
        lightboxImg.src = imageUrl;
        lightbox.style.display = 'flex'; // Use flex to center content
        // Add a class for animation after a small delay
        setTimeout(() => {
            lightbox.classList.add('active');
        }, 10);
    };

    window.closeLightbox = () => {
        lightbox.classList.remove('active');
        // Wait for animation to finish before hiding display
        setTimeout(() => {
            lightbox.style.display = 'none';
            lightboxImg.src = ''; // Clear image src
        }, 300); // Match CSS transition duration
    };
});

async function fetchAlbums() {
    const albumListDiv = document.getElementById('album-list');
    albumListDiv.innerHTML = 'Loading albums...';

    try {
        const response = await fetch('/api/albums');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const albums = await response.json();

        albumListDiv.innerHTML = ''; // Clear loading message

        if (albums.length === 0) {
            albumListDiv.innerHTML = '<p style="text-align: center; width: 100%;">No albums found. Please add photos to your "photos" directory.</p>';
            return;
        }

        albums.forEach(album => {
            const albumCard = document.createElement('a'); // Use <a> for navigation
            albumCard.href = `/album/${encodeURIComponent(album.name)}`; // Encode for URL safety
            albumCard.classList.add('album-card');

            const albumImg = document.createElement('img');
            albumImg.src = album.cover_thumbnail_url;
            albumImg.alt = `Cover for ${album.name}`;
            albumImg.classList.add('album-card-img');
            // Add error handling for image loading
            albumImg.onerror = () => {
                albumImg.src = 'https://placehold.co/200x180/e9ecef/495057?text=No+Image'; // Placeholder if cover fails
            };

            const albumInfo = document.createElement('div');
            albumInfo.classList.add('album-card-info');

            const albumTitle = document.createElement('h2');
            albumTitle.classList.add('album-card-title');
            albumTitle.textContent = album.name;

            const photoCount = document.createElement('p');
            photoCount.classList.add('album-card-count');
            photoCount.textContent = `${album.photo_count} photos`;

            albumInfo.appendChild(albumTitle);
            albumInfo.appendChild(photoCount);
            albumCard.appendChild(albumImg);
            albumCard.appendChild(albumInfo);
            albumListDiv.appendChild(albumCard);
        });
    } catch (error) {
        console.error('Error fetching albums:', error);
        albumListDiv.innerHTML = `<p style="text-align: center; width: 100%; color: red;">Failed to load albums: ${error.message}</p>`;
    }
}

async function fetchPhotos(albumName) {
    const photoGridDiv = document.getElementById('photo-grid');
    photoGridDiv.innerHTML = 'Loading photos...';

    try {
        const response = await fetch(`/api/album/${encodeURIComponent(albumName)}/photos`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const photos = await response.json();

        photoGridDiv.innerHTML = ''; // Clear loading message

        if (photos.length === 0) {
            photoGridDiv.innerHTML = '<p style="text-align: center; width: 100%;">No photos found in this album.</p>';
            return;
        }

        photos.forEach(photo => {
            const photoThumbnailDiv = document.createElement('div');
            photoThumbnailDiv.classList.add('photo-thumbnail');
            photoThumbnailDiv.setAttribute('data-original-url', photo.original_url); // Store original URL

            const photoImg = document.createElement('img');
            photoImg.src = photo.thumbnail_url;
            photoImg.alt = photo.original_filename;
            // Add error handling for image loading
            photoImg.onerror = () => {
                photoImg.src = 'https://placehold.co/200x200/e9ecef/495057?text=No+Image'; // Placeholder if thumbnail fails
            };

            photoThumbnailDiv.appendChild(photoImg);

            // Add click listener to open lightbox
            photoThumbnailDiv.addEventListener('click', () => {
                openLightbox(photoThumbnailDiv.getAttribute('data-original-url'));
            });

            photoGridDiv.appendChild(photoThumbnailDiv);
        });
    } catch (error) {
        console.error(`Error fetching photos for album ${albumName}:`, error);
        photoGridDiv.innerHTML = `<p style="text-align: center; width: 100%; color: red;">Failed to load photos: ${error.message}</p>`;
    }
}

