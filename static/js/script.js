// static/js/script.js

// Global variables for lightbox navigation
let currentAlbumPhotos = []; // Stores the list of photos for the current album
let currentPhotoIndex = 0; // Stores the index of the currently displayed photo
let currentAlbumName = ''; // Stores the name of the currently viewed album
let focusedElementBeforeLightbox = null; // Store the element that was focused before opening lightbox

// Pinch-to-zoom variables
let isZoomed = false;
let initialScale = 1;
let currentScale = 1;
let maxScale = 4;
let minScale = 1;
let lastPinchDistance = 0;
let imageTransform = { x: 0, y: 0, scale: 1 };
let isPanning = false;
let panStartX = 0;
let panStartY = 0;
let initialTransformX = 0;
let initialTransformY = 0;

// Dynamically determine the base URL prefix from window.location.pathname
function getBaseUrlPrefix() {
    const pathSegments = window.location.pathname.split('/').filter(s => s.length > 0);
    const knownAppRoots = ['static', 'api', 'album', 'photos', 'thumbnails'];
    if (pathSegments.length > 0 && !knownAppRoots.includes(pathSegments[0])) {
        return '/' + pathSegments[0];
    }
    return ''; // App is at root (or first segment is an app-specific route)
}

const BASE_URL_PREFIX = getBaseUrlPrefix();

// Utility function to calculate distance between two touch points
function getTouchDistance(touch1, touch2) {
    const dx = touch1.clientX - touch2.clientX;
    const dy = touch1.clientY - touch2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
}

// Utility function to get center point between two touches
function getTouchCenter(touch1, touch2) {
    return {
        x: (touch1.clientX + touch2.clientX) / 2,
        y: (touch1.clientY + touch2.clientY) / 2
    };
}

// Utility function to apply transform to image
function applyImageTransform(img, transform) {
    img.style.transform = `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`;
}

// Utility function to reset image transform
function resetImageTransform(img) {
    imageTransform = { x: 0, y: 0, scale: 1 };
    currentScale = 1;
    isZoomed = false;
    applyImageTransform(img, imageTransform);
}

// Utility function to constrain pan based on image bounds
function constrainPan(img, transform) {
    const rect = img.getBoundingClientRect();
    const containerRect = img.parentElement.getBoundingClientRect();
    
    // Only constrain if image is larger than container
    if (rect.width > containerRect.width) {
        const maxX = (rect.width - containerRect.width) / 2;
        transform.x = Math.max(-maxX, Math.min(maxX, transform.x));
    } else {
        transform.x = 0;
    }
    
    if (rect.height > containerRect.height) {
        const maxY = (rect.height - containerRect.height) / 2;
        transform.y = Math.max(-maxY, Math.min(maxY, transform.y));
    } else {
        transform.y = 0;
    }
    
    return transform;
}

// Utility function to show loading indicator
function showLoading(message = 'Loading...') {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
        const srOnlyText = loadingIndicator.querySelector('.sr-only');
        if (srOnlyText) {
            srOnlyText.textContent = message;
        }
    }
}

// Utility function to hide loading indicator
function hideLoading() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

// Utility function to show error message
function showError(message) {
    hideLoading();
    const errorContainer = document.getElementById('error-message');
    if (errorContainer) {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
        errorContainer.setAttribute('aria-live', 'assertive');
    }
}

// Utility function to hide error message
function hideError() {
    const errorContainer = document.getElementById('error-message');
    if (errorContainer) {
        errorContainer.style.display = 'none';
    }
}

// Utility function to announce to screen readers
function announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;
    document.body.appendChild(announcement);
    
    // Remove the announcement after it's been read
    setTimeout(() => {
        document.body.removeChild(announcement);
    }, 1000);
}

document.addEventListener('DOMContentLoaded', () => {
    // Determine if we are on the main gallery page or an album page
    const pathname = window.location.pathname;
    
    // Construct the expected path for the main gallery page dynamically
    const galleryRootPath = BASE_URL_PREFIX + '/';
    const albumRootPath = BASE_URL_PREFIX + '/album/'; // e.g., /gallery/album/

    if (pathname === galleryRootPath || (BASE_URL_PREFIX === '' && pathname === '/')) {
        showLoading('Loading photo albums...');
        fetchAlbums(); // This now fetches mode and albums/photos
    } else if (pathname.startsWith(albumRootPath)) {
        const albumPathEncoded = pathname.substring(albumRootPath.length);
        
        // currentAlbumName in JS will be '__root__' for the root album, or the decoded path for others.
        // This is the identifier used in API calls.
        currentAlbumName = albumPathEncoded; 
        
        // Update display title based on this identifier
        if (albumPathEncoded === '__root__') {
            document.getElementById('album-title').textContent = 'Album: Root Gallery';
        } else {
            document.getElementById('album-title').textContent = `Album: ${decodeURIComponent(albumPathEncoded).replace(/\//g, ' / ')}`;
        }
        
        if (currentAlbumName) {
            showLoading('Loading photos...');
            initializeAlbumPage(); // Will call fetchPhotos using currentAlbumName (__root__ or path)
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

    // Attach event listeners only if elements are found
    if (closeBtn) {
        closeBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            closeLightbox();
        });
    }

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

    if (lightbox) {
        lightbox.addEventListener('click', (event) => {
            if (event.target === lightbox) {
                closeLightbox();
            }
        });
    }

    // Enhanced keyboard navigation for lightbox
    document.addEventListener('keydown', (event) => {
        if (lightbox && lightbox.classList.contains('active')) {
            switch (event.key) {
                case 'ArrowLeft':
                    event.preventDefault();
                    if (!isZoomed) showPrevPhoto();
                    break;
                case 'ArrowRight':
                    event.preventDefault();
                    if (!isZoomed) showNextPhoto();
                    break;
                case 'Escape':
                    event.preventDefault();
                    closeLightbox();
                    break;
                case 'Home':
                    event.preventDefault();
                    if (!isZoomed) showFirstPhoto();
                    break;
                case 'End':
                    event.preventDefault();
                    if (!isZoomed) showLastPhoto();
                    break;
                case 'Tab':
                    // Trap focus within lightbox
                    trapFocus(event, lightbox);
                    break;
                case '0':
                    // Reset zoom with '0' key
                    event.preventDefault();
                    if (lightboxImg) {
                        resetImageTransform(lightboxImg);
                        announceToScreenReader('Image zoom reset');
                    }
                    break;
                case '+':
                case '=':
                    // Zoom in
                    event.preventDefault();
                    if (lightboxImg) {
                        zoomImage(lightboxImg, 1.2);
                    }
                    break;
                case '-':
                case '_':
                    // Zoom out
                    event.preventDefault();
                    if (lightboxImg) {
                        zoomImage(lightboxImg, 0.8);
                    }
                    break;
            }
        }
    });

    // Enhanced touch gesture support for lightbox
    let touchStartX = 0;
    let touchStartY = 0;
    let touchStartTime = 0;
    let lastTouchTime = 0;
    let touchCount = 0;
    const swipeThreshold = 50;
    const doubleTapThreshold = 300;

    if (lightboxImg) {
        // Multi-touch gesture handling
        lightboxImg.addEventListener('touchstart', (e) => {
            const now = Date.now();
            touchCount = e.touches.length;
            
            if (touchCount === 1) {
                // Single touch - potential swipe or pan
                const touch = e.touches[0];
                touchStartX = touch.clientX;
                touchStartY = touch.clientY;
                touchStartTime = now;
                
                // Check for double tap
                if (now - lastTouchTime < doubleTapThreshold) {
                    handleDoubleTap(touch);
                    e.preventDefault();
                    return;
                }
                lastTouchTime = now;
                
                // If image is zoomed, prepare for panning
                if (isZoomed) {
                    isPanning = true;
                    panStartX = touch.clientX;
                    panStartY = touch.clientY;
                    initialTransformX = imageTransform.x;
                    initialTransformY = imageTransform.y;
                }
            } else if (touchCount === 2) {
                // Two touches - pinch gesture
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                lastPinchDistance = getTouchDistance(touch1, touch2);
                e.preventDefault();
            }
        });

        lightboxImg.addEventListener('touchmove', (e) => {
            if (touchCount === 1) {
                // Single touch - pan if zoomed
                if (isZoomed && isPanning) {
                    e.preventDefault();
                    const touch = e.touches[0];
                    const deltaX = touch.clientX - panStartX;
                    const deltaY = touch.clientY - panStartY;
                    
                    imageTransform.x = initialTransformX + deltaX;
                    imageTransform.y = initialTransformY + deltaY;
                    
                    // Constrain pan to image bounds
                    imageTransform = constrainPan(lightboxImg, imageTransform);
                    applyImageTransform(lightboxImg, imageTransform);
                }
            } else if (touchCount === 2) {
                // Two touches - pinch zoom
                e.preventDefault();
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                const currentDistance = getTouchDistance(touch1, touch2);
                
                if (lastPinchDistance > 0) {
                    const scaleChange = currentDistance / lastPinchDistance;
                    const newScale = currentScale * scaleChange;
                    
                    // Constrain scale
                    const constrainedScale = Math.max(minScale, Math.min(maxScale, newScale));
                    
                    if (constrainedScale !== currentScale) {
                        const center = getTouchCenter(touch1, touch2);
                        const rect = lightboxImg.getBoundingClientRect();
                        const centerX = center.x - rect.left - rect.width / 2;
                        const centerY = center.y - rect.top - rect.height / 2;
                        
                        // Adjust transform to zoom into touch center
                        imageTransform.x = centerX - centerX * (constrainedScale / currentScale);
                        imageTransform.y = centerY - centerY * (constrainedScale / currentScale);
                        imageTransform.scale = constrainedScale;
                        
                        currentScale = constrainedScale;
                        isZoomed = currentScale > 1;
                        
                        applyImageTransform(lightboxImg, imageTransform);
                    }
                }
                
                lastPinchDistance = currentDistance;
            }
        }, { passive: false });

        lightboxImg.addEventListener('touchend', (e) => {
            const now = Date.now();
            
            if (touchCount === 1 && !isPanning) {
                // Single touch ended - check for swipe
                const touch = e.changedTouches[0];
                const touchEndX = touch.clientX;
                const touchEndY = touch.clientY;
                const deltaX = touchEndX - touchStartX;
                const deltaY = touchEndY - touchStartY;
                const timeDelta = now - touchStartTime;
                
                // Only process swipes if not zoomed and quick enough
                if (!isZoomed && timeDelta < 300 && Math.abs(deltaX) > Math.abs(deltaY)) {
                    if (deltaX > swipeThreshold) {
                        showPrevPhoto();
                        announceToScreenReader('Showing previous image');
                    } else if (deltaX < -swipeThreshold) {
                        showNextPhoto();
                        announceToScreenReader('Showing next image');
                    }
                }
            }
            
            // Reset touch state
            isPanning = false;
            touchCount = 0;
            lastPinchDistance = 0;
        });
    }

    // Double tap handler for zoom toggle
    function handleDoubleTap(touch) {
        if (!lightboxImg) return;
        
        if (isZoomed) {
            // Reset zoom
            resetImageTransform(lightboxImg);
            announceToScreenReader('Image zoom reset');
        } else {
            // Zoom in to 2x at tap location
            const rect = lightboxImg.getBoundingClientRect();
            const centerX = touch.clientX - rect.left - rect.width / 2;
            const centerY = touch.clientY - rect.top - rect.height / 2;
            
            const zoomScale = 2;
            imageTransform.x = -centerX * (zoomScale - 1);
            imageTransform.y = -centerY * (zoomScale - 1);
            imageTransform.scale = zoomScale;
            
            currentScale = zoomScale;
            isZoomed = true;
            
            applyImageTransform(lightboxImg, imageTransform);
            announceToScreenReader('Image zoomed in');
        }
    }

    // Zoom function for keyboard controls
    function zoomImage(img, scaleFactor) {
        const newScale = Math.max(minScale, Math.min(maxScale, currentScale * scaleFactor));
        
        if (newScale !== currentScale) {
            const scaleChange = newScale / currentScale;
            
            // Zoom into center
            imageTransform.x = imageTransform.x * scaleChange;
            imageTransform.y = imageTransform.y * scaleChange;
            imageTransform.scale = newScale;
            
            currentScale = newScale;
            isZoomed = currentScale > 1;
            
            // Constrain pan after zoom
            imageTransform = constrainPan(img, imageTransform);
            applyImageTransform(img, imageTransform);
            
            announceToScreenReader(`Image zoom: ${Math.round(currentScale * 100)}%`);
        }
    }

    // Focus trap function for lightbox
    function trapFocus(event, container) {
        const focusableElements = container.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])'
        );
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (event.shiftKey) {
            if (document.activeElement === firstElement) {
                lastElement.focus();
                event.preventDefault();
            }
        } else {
            if (document.activeElement === lastElement) {
                firstElement.focus();
                event.preventDefault();
            }
        }
    }

    // Enhanced openLightbox function with zoom reset
    window.openLightbox = (index, photosArray) => {
        if (!lightbox || !lightboxImg) {
            console.error("Lightbox elements not found. Cannot open lightbox.");
            return;
        }
        
        // Store the currently focused element
        focusedElementBeforeLightbox = document.activeElement;
        
        // Reset zoom state
        resetImageTransform(lightboxImg);
        
        currentPhotoIndex = index;
        currentAlbumPhotos = photosArray;

        lightbox.style.display = 'flex'; 
        updateLightboxImage(); 

        requestAnimationFrame(() => {
            lightbox.classList.add('active');
            // Focus the close button initially
            closeBtn.focus();
            announceToScreenReader(`Image viewer opened. Image ${index + 1} of ${photosArray.length}`);
        });
    };

    // Enhanced closeLightbox function with zoom reset
    window.closeLightbox = () => {
        if (!lightbox || !lightboxImg) {
            console.error("Lightbox elements not found. Cannot close lightbox.");
            return;
        }
        
        lightbox.classList.remove('active');
        announceToScreenReader('Image viewer closed');
        
        // Reset zoom state
        resetImageTransform(lightboxImg);
        
        setTimeout(() => {
            lightbox.style.display = 'none';
            lightboxImg.src = '';
            
            // Restore focus to the element that was focused before opening lightbox
            if (focusedElementBeforeLightbox) {
                focusedElementBeforeLightbox.focus();
                focusedElementBeforeLightbox = null;
            }
        }, 300); // Match CSS transition duration
    };

    // Helper function that updates the displayed image and navigation buttons
    function updateLightboxImage() {
        if (!lightboxImg || !prevBtn || !nextBtn || !downloadBtn) {
             console.warn("updateLightboxImage: Required lightbox elements not found. Skipping update.");
             return;
        }

        if (currentAlbumPhotos.length > 0 && currentPhotoIndex >= 0 && currentPhotoIndex < currentAlbumPhotos.length) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            
            // Reset zoom when changing images
            resetImageTransform(lightboxImg);
            
            lightboxImg.src = photo.original_url;
            lightboxImg.alt = `Photo: ${photo.original_filename}`;

            // Update ARIA descriptions
            const description = document.getElementById('lightbox-description');
            if (description) {
                description.textContent = `Image ${currentPhotoIndex + 1} of ${currentAlbumPhotos.length}: ${photo.original_filename}. Double-tap to zoom, pinch to zoom and pan.`;
            }

            // Update navigation button states
            prevBtn.style.display = (currentPhotoIndex > 0) ? 'flex' : 'none';
            nextBtn.style.display = (currentPhotoIndex < currentAlbumPhotos.length - 1) ? 'flex' : 'none';
            
            // Update button ARIA attributes
            if (currentPhotoIndex > 0) {
                prevBtn.setAttribute('aria-label', `Previous image (${currentPhotoIndex} of ${currentAlbumPhotos.length})`);
            }
            if (currentPhotoIndex < currentAlbumPhotos.length - 1) {
                nextBtn.setAttribute('aria-label', `Next image (${currentPhotoIndex + 2} of ${currentAlbumPhotos.length})`);
            }

            if (downloadBtn) {
                downloadBtn.setAttribute('download', photo.original_filename);
                downloadBtn.setAttribute('aria-label', `Download ${photo.original_filename}`);
            }
        } else {
            console.warn("updateLightboxImage: No photos data or invalid index. Cannot update lightbox image.");
        }
    }

    function showNextPhoto() {
        if (currentPhotoIndex < currentAlbumPhotos.length - 1) {
            currentPhotoIndex++;
            updateLightboxImage();
            announceToScreenReader(`Image ${currentPhotoIndex + 1} of ${currentAlbumPhotos.length}`);
        }
    }

    function showPrevPhoto() {
        if (currentPhotoIndex > 0) {
            currentPhotoIndex--;
            updateLightboxImage();
            announceToScreenReader(`Image ${currentPhotoIndex + 1} of ${currentAlbumPhotos.length}`);
        }
    }

    function showFirstPhoto() {
        if (currentAlbumPhotos.length > 0) {
            currentPhotoIndex = 0;
            updateLightboxImage();
            announceToScreenReader(`First image: ${currentPhotoIndex + 1} of ${currentAlbumPhotos.length}`);
        }
    }

    function showLastPhoto() {
        if (currentAlbumPhotos.length > 0) {
            currentPhotoIndex = currentAlbumPhotos.length - 1;
            updateLightboxImage();
            announceToScreenReader(`Last image: ${currentPhotoIndex + 1} of ${currentAlbumPhotos.length}`);
        }
    }

    function downloadCurrentImage() {
        if (currentAlbumPhotos.length > 0 && currentPhotoIndex >= 0 && currentPhotoIndex < currentAlbumPhotos.length) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            const link = document.createElement('a');
            link.href = photo.original_url;
            link.download = photo.original_filename;
            link.setAttribute('aria-label', `Download ${photo.original_filename}`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            announceToScreenReader(`Downloading ${photo.original_filename}`);
        }
    }

    function copyShareLink() {
        if (currentAlbumPhotos.length > 0 && currentPhotoIndex >= 0 && currentPhotoIndex < currentAlbumPhotos.length) {
            const photo = currentAlbumPhotos[currentPhotoIndex];
            const shareUrl = window.location.origin + photo.original_url;
            
            navigator.clipboard.writeText(shareUrl).then(() => {
                showMessage('Link copied to clipboard!');
                announceToScreenReader('Image link copied to clipboard');
            }).catch(() => {
                showMessage('Failed to copy link');
                announceToScreenReader('Failed to copy image link');
            });
        }
    }

    function showMessage(text) {
        if (messageBox) {
            messageBox.textContent = text;
            messageBox.classList.add('show');
            setTimeout(() => {
                messageBox.classList.remove('show');
            }, 3000);
        }
    }

    function getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    async function initializeAlbumPage() {
        try {
            await fetchPhotos(currentAlbumName);
        } catch (error) {
            console.error('Error initializing album page:', error);
            showError('Failed to load album photos');
        }
    }
});

// Enhanced fetchAlbums function with accessibility
async function fetchAlbums() {
    try {
        hideError();
        
        const response = await fetch(`${BASE_URL_PREFIX}/api/albums`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        hideLoading();
        
        const albumListElement = document.getElementById('album-list');
        if (!albumListElement) {
            throw new Error('Album list element not found');
        }
        
        albumListElement.innerHTML = '';
        
        if (data.albums && data.albums.length > 0) {
            data.albums.forEach((album, index) => {
                const albumElement = createAlbumElement(album, index);
                albumListElement.appendChild(albumElement);
            });
            announceToScreenReader(`${data.albums.length} photo albums loaded`);
        } else {
            albumListElement.innerHTML = '<div class="empty-album-message" role="status"><p>No albums found.</p></div>';
            announceToScreenReader('No photo albums found');
        }
    } catch (error) {
        console.error('Error fetching albums:', error);
        showError('Failed to load photo albums');
        announceToScreenReader('Failed to load photo albums');
    }
}

// Enhanced createAlbumElement function with accessibility
function createAlbumElement(album, index) {
    const albumCard = document.createElement('a');
    albumCard.href = `${BASE_URL_PREFIX}/album/${encodeURIComponent(album.name)}`;
    albumCard.className = 'album-card';
    albumCard.setAttribute('role', 'link');
    albumCard.setAttribute('aria-label', `View album ${album.name} with ${album.photo_count} photos`);
    albumCard.setAttribute('tabindex', '0');
    
    const albumImg = document.createElement('div');
    albumImg.className = 'album-card-img';
    albumImg.setAttribute('aria-hidden', 'true');
    
    if (album.cover_image_url) {
        const img = document.createElement('img');
        img.src = album.cover_image_url;
        img.alt = '';
        img.setAttribute('aria-hidden', 'true');
        img.loading = 'lazy';
        albumImg.appendChild(img);
    } else {
        albumImg.innerHTML = `
            <svg width="100" height="100" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <rect width="100" height="100" fill="#f0f0f0"/>
                <path d="M25 25h50v50H25z" fill="#ddd"/>
                <circle cx="40" cy="40" r="8" fill="#bbb"/>
                <path d="M25 65l15-15 10 10 15-20 10 10v15H25z" fill="#bbb"/>
            </svg>
        `;
    }
    
    const albumInfo = document.createElement('div');
    albumInfo.className = 'album-card-info';
    
    const albumTitle = document.createElement('h3');
    albumTitle.className = 'album-card-title';
    albumTitle.textContent = album.name;
    
    const albumCount = document.createElement('p');
    albumCount.className = 'album-card-count';
    albumCount.textContent = `${album.photo_count} photo${album.photo_count !== 1 ? 's' : ''}`;
    
    albumInfo.appendChild(albumTitle);
    albumInfo.appendChild(albumCount);
    
    albumCard.appendChild(albumImg);
    albumCard.appendChild(albumInfo);
    
    // Add keyboard support
    albumCard.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            albumCard.click();
        }
    });
    
    return albumCard;
}

// Enhanced fetchPhotos function with accessibility
async function fetchPhotos(albumName) {
    try {
        hideError();

        // Build the correct API endpoint based on album name
        let apiUrl;
        if (albumName === '__root__') {
            apiUrl = `${BASE_URL_PREFIX}/api/album/__root__`;
        } else {
            const encodedAlbumName = encodeURIComponent(albumName);
            apiUrl = `${BASE_URL_PREFIX}/api/album/${encodedAlbumName}/photos`;
        }

        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        hideLoading();

        const photoGridElement = document.getElementById('photo-grid');
        if (!photoGridElement) {
            throw new Error('Photo grid element not found');
        }

        photoGridElement.innerHTML = '';

        // The API returns an array directly, not wrapped in a 'photos' property
        if (Array.isArray(data) && data.length > 0) {
            data.forEach((photo, index) => {
                const photoElement = createPhotoElement(photo, index, data);
                photoGridElement.appendChild(photoElement);
            });
            announceToScreenReader(`${data.length} photos loaded in album`);
        } else {
            const emptyMessage = document.getElementById('empty-album-message');
            if (emptyMessage) {
                emptyMessage.style.display = 'block';
            }
            announceToScreenReader('No photos found in this album');
        }
    } catch (error) {
        console.error('Error fetching photos:', error);
        showError('Failed to load album photos');
        announceToScreenReader('Failed to load album photos');
    }
}

// Enhanced createPhotoElement function with accessibility
function createPhotoElement(photo, index, photosArray) {
    const photoThumbnail = document.createElement('div');
    photoThumbnail.className = 'photo-thumbnail';
    photoThumbnail.setAttribute('role', 'button');
    photoThumbnail.setAttribute('aria-label', `View photo ${photo.original_filename}`);
    photoThumbnail.setAttribute('tabindex', '0');
    
    const img = document.createElement('img');
    img.src = photo.thumbnail_url;
    img.alt = `Photo: ${photo.original_filename}`;
    img.loading = 'lazy';
    
    photoThumbnail.appendChild(img);
    
    // Add click handler
    photoThumbnail.addEventListener('click', () => {
        openLightbox(index, photosArray);
    });
    
    // Add keyboard support
    photoThumbnail.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openLightbox(index, photosArray);
        }
    });
    
    return photoThumbnail;
}

