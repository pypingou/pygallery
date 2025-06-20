// static/js/script.js

// Global variables for lightbox navigation
let currentAlbumPhotos = []; // Stores the list of photos for the current album
let currentPhotoIndex = 0; // Stores the index of the currently displayed photo
let currentAlbumName = ''; // Stores the name of the currently viewed album

// NEW: Dynamically determine the base URL prefix from window.location.pathname
// This function determines the segment of the path that represents the app's mount point.
function getBaseUrlPrefix() {
    const pathSegments = window.location.pathname.split('/').filter(s => s.length > 0);
    // If the first segment is "static", "api", "album", "photos", "thumbnails",
    // it means the app is likely at the root.
    // Otherwise, the first segment is probably the BASE_URL_PREFIX.
    const knownAppRoots = ['static', 'api', 'album', 'photos', 'thumbnails'];
    if (pathSegments.length > 0 && !knownAppRoots.includes(pathSegments[0])) {
        return '/' + pathSegments[0];
    }
    return ''; // App is at root (or first segment is an app-specific route)
}

const BASE_URL_PREFIX = getBaseUrlPrefix();


document.addEventListener('DOMContentLoaded', () => {
    // Determine if we are on the main gallery page or an album page
    const pathname = window.location.pathname;
    
    // Construct the expected path for the main gallery page dynamically
    const galleryRootPath = BASE_URL_PREFIX + '/';
    const albumRootPath = BASE_URL_PREFIX + '/album/'; // e.g., /gallery/album/

    // Adjust conditions to strictly match based on dynamically found prefix
    if (pathname === galleryRootPath || (BASE_URL_PREFIX === '' && pathname === '/')) { // Handle /gallery/ and / (for root)
        fetchAlbums();
    } else if (pathname.startsWith(albumRootPath)) {
        // Example: /gallery/album/Family/Vacation/Paris -> albumPathEncoded = Family/Vacation/Paris
        const albumPathEncoded = pathname.substring(albumRootPath.length);
        const albumName = decodeURIComponent(albumPathEncoded); // Decode it once
        currentAlbumName = albumName; // Store globally
        
        if (currentAlbumName) {
            document.getElementById('album-title').textContent = `Album: ${currentAlbumName.replace(/\//g, ' / ')}`;
            initializeAlbumPage(); // This will call fetchPhotos and then handle the image parameter
        }
    }

    // Lightbox functionality
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const closeBtn = document.querySelector('.close-btn');
    const prevBtn = document.getElementById('prev-photo-btn');
    const nextBtn = document.getElementById('next-photo-btn');
    const downloadBtn = document.getElementById('download-photo-btn');
    const shareBtn = document.getElementById('share-photo-btn');
    const messageBox = document.getElementById('message-box');

    closeBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        closeLightbox();
    });

    if (prevBtn) {
        prevBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            showPrevPhoto();
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            showNextPhoto();
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            downloadCurrentImage();
        });
    }

    if (shareBtn) {
        shareBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            copyShareLink();
        });
    }

    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (lightbox.classList.contains('active')) {
            if (event.key === 'ArrowLeft') {
                showPrevPhoto();
            } else if (event.key === 'ArrowRight') {
                showNextPhoto();
            } else if (event.key === 'Escape') {
                closeLightbox();
            }
        }
    });

    window.openLightbox = (index, photosArray) => {
        currentPhotoIndex = index;
        currentAlbumPhotos = photosArray;

        updateLightboxImage();

        lightbox.style.display = 'flex';
        setTimeout(() => {
            lightbox.classList.add('active');
        }, 10);
    };

    window.closeLightbox = () => {
        lightbox.classList.remove('active');
        setTimeout(() => {
            lightbox.style.display = 'none';
            lightboxImg.src = '';
            currentAlbumPhotos = [];
            currentPhotoIndex = 0;
            currentAlbumName = '';
        }, 300);
    };

    function updateLightboxImage() {
        if (currentAlbumPhotos.length > 0 && currentPhotoIndex >= 0 && currentPhotoIndex < currentAlbumPhotos.length) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            lightboxImg.src = photo.original_url;
            lightboxImg.alt = photo.original_filename;

            prevBtn.style.display = (currentPhotoIndex > 0) ? 'flex' : 'none';
            nextBtn.style.display = (currentPhotoIndex < currentAlbumPhotos.length - 1) ? 'flex' : 'none';

            if (downloadBtn) {
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

    function downloadCurrentImage() {
        if (currentAlbumPhotos.length > 0) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            const imageUrl = photo.original_url;
            const filename = photo.original_filename;

            const a = document.createElement('a');
            a.href = imageUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    }

    function copyShareLink() {
        if (currentAlbumPhotos.length > 0 && currentAlbumName) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            // Construct the shareable URL using the full current window location origin + derived prefix
            // The BASE_URL_PREFIX from getBaseUrlPrefix() is already included in window.location.origin for shared links
            const shareUrl = `${window.location.origin}${window.location.pathname.split('?')[0]}?image=${encodeURIComponent(photo.original_filename)}`;

            const tempInput = document.createElement('input');
            tempInput.value = shareUrl;
            document.body.appendChild(tempInput);
            tempInput.select();
            document.execCommand('copy');
            document.body.removeChild(tempInput);

            if (messageBox) {
                messageBox.textContent = 'Link copied to clipboard!';
                messageBox.classList.add('show');
                setTimeout(() => {
                    messageBox.classList.remove('show');
                }, 3000);
            }
        }
    }

    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        var results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    async function initializeAlbumPage() {
        const photos = await fetchPhotos(currentAlbumName);
        if (photos.length > 0) {
            const imageUrlParam = getUrlParameter('image');
            if (imageUrlParam) {
                const foundIndex = photos.findIndex(photo => photo.original_filename === imageUrlParam);
                if (foundIndex !== -1) {
                    openLightbox(foundIndex, photos);
                } else {
                    console.warn(`Image '${imageUrlParam}' not found in album '${currentAlbumName}'.`);
                }
            }
        }
    }
});

async function fetchAlbums() {
    const albumListDiv = document.getElementById('album-list');
    albumListDiv.innerHTML = 'Loading albums...';

    try {
        // Use BASE_URL_PREFIX for API calls
        const response = await fetch(`${BASE_URL_PREFIX}/api/albums`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const albums = await response.json();

        albumListDiv.innerHTML = '';

        if (albums.length === 0) {
            albumListDiv.innerHTML = '<p style="text-align: center; width: 100%;">No albums found. Please add photos to your "photos" directory.</p>';
            return;
        }

        albums.forEach(album => {
            const albumCard = document.createElement('a');
            // Use BASE_URL_PREFIX for album links
            albumCard.href = `${BASE_URL_PREFIX}/album/${album.name}`;
            albumCard.classList.add('album-card');

            const albumImg = document.createElement('img');
            albumImg.src = album.cover_thumbnail_url; // This URL comes directly from Flask
            albumImg.alt = `Cover for ${album.display_name}`;
            albumImg.classList.add('album-card-img');
            albumImg.onerror = () => {
                // The placeholder URL should also be absolute from the domain root
                albumImg.src = `${BASE_URL_PREFIX}/static/placeholder.png`;
            };

            const albumInfo = document.createElement('div');
            albumInfo.classList.add('album-card-info');

            const albumTitle = document.createElement('h2');
            albumTitle.classList.add('album-card-title');
            albumTitle.textContent = album.display_name;
            albumTitle.title = album.name;

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
        // Use BASE_URL_PREFIX for API calls
        const response = await fetch(`${BASE_URL_PREFIX}/api/album/${albumName}/photos`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const photos = await response.json();
        currentAlbumPhotos = photos;

        photoGridDiv.innerHTML = '';

        if (photos.length === 0) {
            photoGridDiv.innerHTML = '<p style="text-align: center; width: 100%;">No photos found in this album.</p>';
            return [];
        }

        photos.forEach((photo, index) => {
            const photoThumbnailDiv = document.createElement('div');
            photoThumbnailDiv.classList.add('photo-thumbnail');

            const photoImg = document.createElement('img');
            photoImg.src = photo.thumbnail_url; // This URL comes directly from Flask
            photoImg.alt = photo.original_filename;
            photoImg.onerror = () => {
                albumImg.src = `${BASE_URL_PREFIX}/static/placeholder.png`;
            };

            photoThumbnailDiv.appendChild(photoImg);

            photoThumbnailDiv.addEventListener('click', () => {
                openLightbox(index, currentAlbumPhotos);
            });

            photoGridDiv.appendChild(photoThumbnailDiv);
        });
        return photos;
    } catch (error) {
        console.error(`Error fetching photos for album ${albumName}:`, error);
        photoGridDiv.innerHTML = `<p style="text-align: center; width: 100%; color: red;">Failed to load photos: ${error.message}</p>`;
        return [];
    }
}

