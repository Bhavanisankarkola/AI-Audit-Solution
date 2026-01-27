let selectedFiles = [];

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const filesList = document.getElementById('fileList');
const filesUl = document.getElementById('files');
const uploadBtn = document.getElementById('uploadBtn');
const cancelBtn = document.getElementById('cancelBtn');

// Click to upload
uploadArea.addEventListener('click', () => fileInput.click());

// File input change
fileInput.addEventListener('change', (e) => {
    addFiles(e.target.files);
});

// Drag and drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
});

function addFiles(files) {
    selectedFiles = Array.from(files);
    updateFileList();
}

function updateFileList() {
    filesUl.innerHTML = '';
    
    if (selectedFiles.length === 0) {
        filesList.classList.remove('show');
        uploadBtn.disabled = true;
        return;
    }
    
    filesList.classList.add('show');
    uploadBtn.disabled = false;

    selectedFiles.forEach((file, index) => {
        const li = document.createElement('li');
        const sizeMB = (file.size / 1024 / 1024).toFixed(2);
        
        li.innerHTML = `
            <span class="file-name">${file.name}</span>
            <span class="file-size">${sizeMB} MB</span>
            <button class="remove-file" onclick="removeFile(${index})">Remove</button>
        `;
        filesUl.appendChild(li);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

cancelBtn.addEventListener('click', () => {
    selectedFiles = [];
    fileInput.value = '';
    updateFileList();
});

uploadBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;

    const formData = new FormData();
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });

    // Show processing
    document.getElementById('processing').style.display = 'block';
    uploadArea.style.display = 'none';
    filesList.classList.remove('show');
    uploadBtn.disabled = true;
    cancelBtn.disabled = true;

    // Simulate progress
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    let progress = 0;

    const progressInterval = setInterval(() => {
        progress += Math.random() * 25;
        if (progress > 85) progress = 85;
        progressFill.style.width = progress + '%';
        progressText.textContent = Math.floor(progress) + '%';
    }, 300);

    try {
        // Send files to server
        const response = await fetch('/api/upload_documents', {
            method: 'POST',
            body: formData
        });

        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = '100%';

        // Simulate 15 second processing
        await new Promise(resolve => setTimeout(resolve, 15000));

        const data = await response.json();

        if (response.ok) {
            showNotification('Documents uploaded and processed successfully!', 'success');
            selectedFiles = [];
            fileInput.value = '';
            
            // Reset UI
            setTimeout(() => {
                document.getElementById('processing').style.display = 'none';
                uploadArea.style.display = 'block';
                progressFill.style.width = '0%';
                progressText.textContent = '0%';
                uploadBtn.disabled = false;
                cancelBtn.disabled = false;
                
                // Redirect to chat after success
                setTimeout(() => {
                    window.location.href = '/chat';
                }, 1000);
            }, 2000);
        } else {
            showNotification('Error uploading documents. Please try again.', 'error');
            resetUpload();
        }
    } catch (error) {
        console.error('Error:', error);
        clearInterval(progressInterval);
        showNotification('Upload failed. Please try again.', 'error');
        resetUpload();
    }
});

function resetUpload() {
    document.getElementById('processing').style.display = 'none';
    uploadArea.style.display = 'block';
    document.getElementById('progressFill').style.width = '0%';
    document.getElementById('progressText').textContent = '0%';
    uploadBtn.disabled = false;
    cancelBtn.disabled = false;
}

function showNotification(message, type) {
    const notification = document.getElementById('notification');
    const notificationText = document.getElementById('notificationText');
    
    notification.classList.remove('success', 'error');
    notification.classList.add('show', type);
    notificationText.textContent = message;

    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

function closeNotification() {
    document.getElementById('notification').classList.remove('show');
}
