document.addEventListener('DOMContentLoaded', () => {
  const heroSlides = document.querySelectorAll('.hero-slide');
  if (heroSlides.length > 1) {
    let currentIndex = 0;
    setInterval(() => {
      heroSlides[currentIndex].classList.remove('active');
      currentIndex = (currentIndex + 1) % heroSlides.length;
      heroSlides[currentIndex].classList.add('active');
    }, 4000);
  }

  const gallery = document.querySelector('[data-detail-gallery]');
  const gallerySlides = gallery ? Array.from(gallery.querySelectorAll('[data-gallery-slide]')) : [];
  const thumbnails = gallery ? Array.from(gallery.querySelectorAll('[data-gallery-thumbnail]')) : [];
  const galleryCounter = gallery?.querySelector('[data-gallery-counter]');
  const lightbox = document.querySelector('[data-image-lightbox]');
  const lightboxImage = lightbox?.querySelector('[data-lightbox-image]');
  const zoomableImages = Array.from(document.querySelectorAll(
    '.detail-gallery-slide [data-gallery-zoom] img, .detail-image-fallback img'
  ));
  let currentSlide = 0;
  let currentZoomImage = 0;

  const showGallerySlide = (index) => {
    if (!gallerySlides.length) return;
    currentSlide = (index + gallerySlides.length) % gallerySlides.length;
    gallerySlides.forEach((slide, slideIndex) => {
      const active = slideIndex === currentSlide;
      slide.hidden = !active;
      slide.classList.toggle('active', active);
      if (!active) slide.querySelector('video')?.pause();
    });
    thumbnails.forEach((thumbnail, thumbnailIndex) => {
      const active = thumbnailIndex === currentSlide;
      thumbnail.classList.toggle('active', active);
      thumbnail.setAttribute('aria-pressed', String(active));
    });
    if (galleryCounter) galleryCounter.textContent = `${currentSlide + 1} / ${gallerySlides.length}`;
  };

  const imageSlideIndexes = gallerySlides
    .map((slide, index) => slide.querySelector('[data-gallery-zoom] img') ? index : -1)
    .filter((index) => index >= 0);

  const showZoomImage = (imageIndex) => {
    if (!zoomableImages.length || !lightbox || !lightboxImage) return;
    currentZoomImage = (imageIndex + zoomableImages.length) % zoomableImages.length;
    const image = zoomableImages[currentZoomImage];
    lightboxImage.src = image.src;
    lightboxImage.alt = image.alt;
    if (gallery && imageSlideIndexes.length) {
      const slideIndex = imageSlideIndexes[currentZoomImage];
      showGallerySlide(slideIndex);
    }
  };

  gallery?.querySelector('[data-gallery-previous]')?.addEventListener('click', () => showGallerySlide(currentSlide - 1));
  gallery?.querySelector('[data-gallery-next]')?.addEventListener('click', () => showGallerySlide(currentSlide + 1));
  thumbnails.forEach((thumbnail) => {
    thumbnail.addEventListener('click', () => showGallerySlide(Number(thumbnail.dataset.galleryThumbnail)));
  });

  zoomableImages.forEach((image, imageIndex) => {
    image.closest('[data-gallery-zoom]')?.addEventListener('click', () => {
      showZoomImage(imageIndex);
      lightbox.classList.add('open');
      lightbox.setAttribute('aria-hidden', 'false');
      document.body.classList.add('lightbox-open');
      lightbox.querySelector('[data-lightbox-close]')?.focus();
    });
  });

  const closeLightbox = () => {
    if (!lightbox) return;
    lightbox.classList.remove('open');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('lightbox-open');
  };

  lightbox?.querySelector('[data-lightbox-close]')?.addEventListener('click', closeLightbox);
  lightbox?.addEventListener('click', (event) => {
    if (event.target === lightbox) closeLightbox();
  });
  lightbox?.querySelector('[data-lightbox-previous]')?.addEventListener('click', () => {
    showZoomImage(currentZoomImage - 1);
  });
  lightbox?.querySelector('[data-lightbox-next]')?.addEventListener('click', () => {
    showZoomImage(currentZoomImage + 1);
  });
  if (zoomableImages.length < 2) {
    lightbox?.querySelector('[data-lightbox-previous]')?.setAttribute('hidden', '');
    lightbox?.querySelector('[data-lightbox-next]')?.setAttribute('hidden', '');
  }
  document.addEventListener('keydown', (event) => {
    if (!lightbox?.classList.contains('open')) return;
    if (event.key === 'Escape') closeLightbox();
    if (event.key === 'ArrowLeft' && zoomableImages.length > 1) showZoomImage(currentZoomImage - 1);
    if (event.key === 'ArrowRight' && zoomableImages.length > 1) showZoomImage(currentZoomImage + 1);
  });

  const brandSelect = document.getElementById('brand');
  const modelSelect = document.getElementById('model');

  if (brandSelect && modelSelect) {
    brandSelect.addEventListener('change', () => {
      const selectedBrand = brandSelect.value;
      const modelOptions = modelSelect.dataset.models ? JSON.parse(modelSelect.dataset.models) : {};
      const currentBrandModels = modelOptions[selectedBrand] || [];

      modelSelect.innerHTML = '<option value="">All models</option>' +
        currentBrandModels.map(model => `<option value="${model}">${model}</option>`).join('');
    });
  }

  const catalogFields = ['brand', 'model', 'version']
    .map((type) => document.getElementById(type))
    .filter((field) => field && field.list);

  if (catalogFields.length) {
    const catalogOptions = { brand: [], model: [], version: [] };
    const datalists = {
      brand: document.getElementById('brandSuggestions'),
      model: document.getElementById('modelSuggestions'),
      version: document.getElementById('versionSuggestions'),
    };
    const addButtons = document.querySelectorAll('.catalog-add');
    const normalize = (value) => value.trim().toLocaleLowerCase();
    const brandField = document.getElementById('brand');
    const modelField = document.getElementById('model');
    const versionField = document.getElementById('version');
    let lastBrand = brandField.value.trim();
    let lastModel = modelField.value.trim();

    const updateAddButton = (type) => {
      const field = document.getElementById(type);
      const button = document.querySelector(`.catalog-add[data-catalog-type="${type}"]`);
      if (!field || !button) return;
      const value = field.value.trim();
      const hasParent = type === 'brand' || (type === 'model' ? document.getElementById('brand').value.trim() : document.getElementById('brand').value.trim() && document.getElementById('model').value.trim());
      button.hidden = !value || !hasParent || catalogOptions[type].some((option) => normalize(option) === normalize(value));
    };

    const loadCatalogOptions = async (type) => {
      const params = new URLSearchParams({ type });
      if (type !== 'brand') params.set('brand', document.getElementById('brand').value.trim());
      if (type === 'version') params.set('model', document.getElementById('model').value.trim());
      const response = await fetch(`/admin/catalog/options?${params}`);
      if (!response.ok) return;
      const result = await response.json();
      catalogOptions[type] = result.options || [];
      const datalist = datalists[type];
      if (datalist) {
        datalist.replaceChildren(...catalogOptions[type].map((value) => {
          const option = document.createElement('option');
          option.value = value;
          return option;
        }));
      }
      updateAddButton(type);
    };

    const refreshChildren = async () => {
      catalogOptions.model = [];
      catalogOptions.version = [];
      datalists.model?.replaceChildren();
      datalists.version?.replaceChildren();
      await loadCatalogOptions('model');
      await loadCatalogOptions('version');
      updateAddButton('model');
      updateAddButton('version');
    };

    loadCatalogOptions('brand').then(() => {
      refreshChildren();
    });

    brandField.addEventListener('input', refreshChildren);
    brandField.addEventListener('change', () => {
      if (brandField.value.trim() !== lastBrand) {
        lastBrand = brandField.value.trim();
        modelField.value = '';
        versionField.value = '';
        lastModel = '';
        refreshChildren();
      }
    });
    modelField.addEventListener('input', () => {
      loadCatalogOptions('version');
      updateAddButton('model');
    });
    modelField.addEventListener('change', () => {
      if (modelField.value.trim() !== lastModel) {
        lastModel = modelField.value.trim();
        versionField.value = '';
        loadCatalogOptions('version');
      }
    });
    versionField.addEventListener('input', () => updateAddButton('version'));
    brandField.addEventListener('input', () => updateAddButton('brand'));

    addButtons.forEach((button) => {
      button.addEventListener('click', async () => {
        const type = button.dataset.catalogType;
        const value = document.getElementById(type).value.trim();
        const payload = { type, value };
        if (type !== 'brand') payload.brand = document.getElementById('brand').value.trim();
        if (type === 'version') payload.model = document.getElementById('model').value.trim();
        const response = await fetch('/admin/catalog/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
          window.alert(result.message || 'Could not save this catalog value.');
          return;
        }
        await loadCatalogOptions(type);
        updateAddButton(type);
      });
    });
  }

  const modal = document.getElementById('requestModal');
  const modalTitle = document.getElementById('modalTitle');
  const requestTypeInput = document.getElementById('requestTypeInput');
  const testDriveField = document.getElementById('testDriveField');
  const requestForm = document.getElementById('requestForm');
  const messageBox = document.getElementById('requestFormMessage');

  const openModal = (requestType) => {
    if (!modal) return;
    const title = requestType === 'visit' ? 'Request a visit' : 'Request Information';
    modalTitle.textContent = title;
    requestTypeInput.value = requestType;
    const showTestDrive = requestType === 'visit';
    testDriveField.classList.toggle('hidden', !showTestDrive);
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  };

  document.querySelectorAll('.request-trigger').forEach((button) => {
    button.addEventListener('click', () => {
      const requestType = button.dataset.requestType;
      openModal(requestType);
    });
  });

  const closeModal = () => {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    if (messageBox) messageBox.textContent = '';
    if (requestForm) requestForm.reset();
  };

  const closeButton = document.querySelector('.modal-close');
  if (closeButton) {
    closeButton.addEventListener('click', closeModal);
  }

  modal?.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  if (requestForm) {
    requestForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(requestForm);
      const vehicleId = requestForm.dataset.vehicleId;
      const requestType = requestTypeInput.value;
      formData.set('request_type', requestType);

      const response = await fetch(`/request-info/${vehicleId}`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      messageBox.textContent = result.message || 'Your request was sent.';
      if (result.success) {
        setTimeout(() => closeModal(), 1400);
      }
    });
  }
});
