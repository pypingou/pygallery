// static/js/script.js

// Global variables for lightbox navigation
let currentAlbumPhotos = []; // Stores the list of photos for the current album
let currentPhotoIndex = 0; // Stores the index of the currently displayed photo

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
    const prevBtn = document.getElementById('prev-photo-btn');
    const nextBtn = document.getElementById('next-photo-btn');
    const downloadBtn = document.getElementById('download-photo-btn'); // New: Get download button

    closeBtn.addEventListener('click', (event) => {
        event.stopPropagation(); // Prevent click from bubbling to lightbox overlay
        closeLightbox();
    });

    // Add event listeners for navigation buttons
    if (prevBtn) {
        prevBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent closing lightbox
            showPrevPhoto();
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent closing lightbox
            showNextPhoto();
        });
    }

    // New: Add event listener for download button
    if (downloadBtn) {
        downloadBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent closing lightbox
            downloadCurrentImage();
        });
    }


    // Close lightbox when clicking directly on the overlay (not image or buttons)
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    // Keyboard navigation for lightbox
    document.addEventListener('keydown', (event) => {
        if (lightbox.classList.contains('active')) { // Only active if lightbox is open
            if (event.key === 'ArrowLeft') {
                showPrevPhoto();
            } else if (event.key === 'ArrowRight') {
                showNextPhoto();
            } else if (event.key === 'Escape') {
                closeLightbox();
            }
        }
    });

    // Attach openLightbox to global scope for easy access from dynamically created elements
    // This function now takes the index and the full array of photos
    window.openLightbox = (index, photosArray) => {
        currentPhotoIndex = index;
        currentAlbumPhotos = photosArray; // Store the full list of photos

        updateLightboxImage(); // Show the current photo

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
            currentAlbumPhotos = []; // Clear stored photos
            currentPhotoIndex = 0; // Reset index
        }, 300); // Match CSS transition duration
    };

    function updateLightboxImage() {
        if (currentAlbumPhotos.length > 0 && currentPhotoIndex >= 0 && currentPhotoIndex < currentAlbumPhotos.length) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            lightboxImg.src = photo.original_url;
            lightboxImg.alt = photo.original_filename;

            // Show/hide navigation buttons based on current index
            prevBtn.style.display = (currentPhotoIndex > 0) ? 'flex' : 'none';
            nextBtn.style.display = (currentPhotoIndex < currentAlbumPhotos.length - 1) ? 'flex' : 'none';

            // Update download button's download attribute
            if (downloadBtn) {
                // The download attribute suggests a filename
                downloadBtn.setAttribute('download', photo.original_filename);
            }
        }
    }

    function showNextPhoto() {
        if (currentPhotoIndex < currentAlbumPhotos.length - 1) {
            currentPhotoIndex++;
            updateLightboxImage();
        }
    }

    function showPrevPhoto() {
        if (currentPhotoIndex > 0) {
            currentPhotoIndex--;
            updateLightboxImage();
        }
    }

    // New: Function to trigger image download
    function downloadCurrentImage() {
        if (currentAlbumPhotos.length > 0) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            const imageUrl = photo.original_url;
            const filename = photo.original_filename;

            // Create a temporary anchor element
            const a = document.createElement('a');
            a.href = imageUrl;
            a.download = filename; // Set the desired filename for download

            // Programmatically click the anchor element to trigger download
            document.body.appendChild(a); // Append to body is required for Firefox
            a.click();
            document.body.removeChild(a); // Clean up
        }
    }
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
        // Store the fetched photos in a global variable for lightbox navigation
        // Make a copy to avoid accidental modification
        currentAlbumPhotos = photos;


        photoGridDiv.innerHTML = ''; // Clear loading message

        if (photos.length === 0) {
            photoGridDiv.innerHTML = '<p style="text-align: center; width: 100%;">No photos found in this album.</p>';
            return;
        }

        photos.forEach((photo, index) => {
            const photoThumbnailDiv = document.createElement('div');
            photoThumbnailDiv.classList.add('photo-thumbnail');
            // Instead of storing original_url directly, we'll pass the index and the full photos array
            // photoThumbnailDiv.setAttribute('data-original-url', photo.original_url); // Removed

            const photoImg = document.createElement('img');
            photoImg.src = photo.thumbnail_url;
            photoImg.alt = photo.original_filename;
            // Add error handling for image loading
            photoImg.onerror = () => {
                photoImg.src = 'https://placehold.co/200x200/e9ecef/495057?text=No+Image'; // Placeholder if thumbnail fails
            };

            photoThumbnailDiv.appendChild(photoImg);

            // Add click listener to open lightbox, passing index and photos array
            photoThumbnailDiv.addEventListener('click', () => {
                openLightbox(index, currentAlbumPhotos); // Pass the index and the full array
            });

            photoGridDiv.appendChild(photoThumbnailDiv);
        });
    } catch (error) {
        console.error(`Error fetching photos for album ${albumName}:`, error);
        photoGridDiv.innerHTML = `<p style="text-align: center; width: 100%; color: red;">Failed to load photos: ${error.message}</p>`;
    }
}

