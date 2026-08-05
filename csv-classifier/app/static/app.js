document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('file-input');
  const dropZone = document.getElementById('drop-zone');
  const fileDetails = document.getElementById('file-details');
  const fileName = document.getElementById('file-name');
  const fileSize = document.getElementById('file-size');
  const columnGroup = document.getElementById('column-selector-group');
  const columnSelect = document.getElementById('column-select');
  const startBtn = document.getElementById('start-btn');

  const uploadSection = document.getElementById('upload-section');
  const progressSection = document.getElementById('progress-section');
  const resultsSection = document.getElementById('results-section');
  const errorSection = document.getElementById('error-section');

  const statusBadge = document.getElementById('current-status-badge');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const steps = document.querySelectorAll('.step');

  const consolidationStat = document.getElementById('consolidation-stat');
  const metricTotalRows = document.getElementById('metric-total-rows');
  const metricUniqueCategories = document.getElementById('metric-unique-categories');
  const metricTotalGroups = document.getElementById('metric-total-groups');
  const summaryTableBody = document.getElementById('summary-table-body');
  const downloadBtn = document.getElementById('download-btn');
  const resetBtn = document.getElementById('reset-btn');
  const retryBtn = document.getElementById('retry-btn');
  const errorMessageText = document.getElementById('error-message-text');

  // Sidebar Elements
  const btnSampleBusiness = document.getElementById('btn-sample-business');
  const btnSampleEcommerce = document.getElementById('btn-sample-ecommerce');
  const clusteringSlider = document.getElementById('clustering-slider');
  const clusteringValLabel = document.getElementById('clustering-val-label');
  const statusPillText = document.getElementById('status-pill-text');

  let selectedFile = null;
  let currentJobId = null;
  let pollInterval = null;

  const stageProgressMap = {
    'pending': 5,
    'ingesting': 15,
    'embedding': 35,
    'clustering': 55,
    'naming': 75,
    'assigning': 90,
    'exporting': 95,
    'completed': 100
  };

  // Check API Health on load
  checkApiHealth();

  async function checkApiHealth() {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        statusPillText.textContent = 'API Online & Ready';
      } else {
        statusPillText.textContent = 'API Degraded';
      }
    } catch {
      statusPillText.textContent = 'API Offline';
    }
  }

  // Interactive Slider Listener
  if (clusteringSlider) {
    clusteringSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      let labelText = 'Balanced';
      if (val < 0.80) labelText = 'Broad';
      else if (val > 0.88) labelText = 'Strict';
      clusteringValLabel.textContent = `${labelText} (${val.toFixed(2)})`;
    });
  }

  // Quick Demo Datasets Handlers
  if (btnSampleBusiness) {
    btnSampleBusiness.addEventListener('click', () => {
      loadSampleCSV('business');
    });
  }

  if (btnSampleEcommerce) {
    btnSampleEcommerce.addEventListener('click', () => {
      loadSampleCSV('ecommerce');
    });
  }

  function loadSampleCSV(type) {
    let csvContent = '';
    let fname = '';
    let targetCol = '';

    if (type === 'business') {
      fname = 'business_services_sample.csv';
      targetCol = 'business_category';
      csvContent = `id,business_category,revenue
1,Plumber,1200
2,Plumbing Service,1450
3,Emergency Plumber,1600
4,Plumbing & Heating,2100
5,Residential Plumber,1150
6,Commercial Plumbing,3400
7,Local Plumber,950
8,HVAC Contractor,2200
9,Heating & AC Repair,1800
10,Air Conditioning Service,1950
11,HVAC Maintenance,2100
12,AC Installation,3200
13,Heating Systems,2700
14,Electrician,1300
15,Electrical Services,1750
16,Residential Electrician,1400
17,Emergency Electrician,1900
18,Licensed Electrician,1650
19,Electrical Wiring,2100
20,Roofing Contractor,4500
21,Roof Repair Service,2300
22,Commercial Roofing,5100
23,Residential Roofers,3800
24,Roof Replacement,6200
25,Emergency Roof Repair,2900
26,Auto Repair Shop,1700
27,Car Mechanics,1550
28,Automotive Maintenance,1850
29,Auto Brake Repair,1400
30,Tire & Alignment Service,1600`;
    } else {
      fname = 'ecommerce_products_sample.csv';
      targetCol = 'product_category';
      csvContent = `sku,product_category,price
SKU-101,Wireless Bluetooth Headphones,89.99
SKU-102,Over-Ear Bluetooth Headphones,129.99
SKU-103,Wireless Earbuds Headphones,49.99
SKU-104,Noise Canceling Wireless Headphones,199.99
SKU-105,Running Athletic Shoes,75.00
SKU-106,Men's Athletic Sneakers,80.00
SKU-107,Sport Running Shoes,69.99
SKU-108,Trail Running Shoes,110.00
SKU-109,Ergonomic Mechanical Keyboard,149.00
SKU-110,Wireless Gaming Keyboard,120.00
SKU-111,RGB Mechanical Gaming Keyboard,99.99
SKU-112,Smart OLED TV 55 Inch,599.99
SKU-113,4K Ultra HD Smart TV,499.99
SKU-114,LED Smart Television 60 Inch,649.99
SKU-115,Stainless Steel Water Bottle,22.50
SKU-116,Insulated Flask Water Bottle,28.00
SKU-117,Sport Hydro Water Bottle,18.99`;
    }

    const blob = new Blob([csvContent], { type: 'text/csv' });
    selectedFile = new File([blob], fname, { type: 'text/csv' });

    fileName.textContent = selectedFile.name;
    fileSize.textContent = `(${formatBytes(selectedFile.size)})`;
    fileDetails.classList.remove('hidden');

    const lines = csvContent.split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    populateColumns(headers);

    // Auto-select target column
    if (headers.includes(targetCol)) {
      columnSelect.value = targetCol;
      startBtn.disabled = false;
    }
  }

  // File Selection
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });

  // Drag & Drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  function handleFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = `(${formatBytes(file.size)})`;
    fileDetails.classList.remove('hidden');

    parseHeaders(file);
  }

  function parseHeaders(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result;
      const lines = text.split(/\r\n|\n/);
      if (lines.length > 0 && lines[0].trim() !== '') {
        const headers = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
        populateColumns(headers);
      }
    };
    // Read first 10KB to parse CSV header
    const blob = file.slice(0, 10240);
    reader.readAsText(blob);
  }

  function populateColumns(headers) {
    columnSelect.innerHTML = '<option value="" disabled selected>-- Select Column --</option>';
    headers.forEach((h) => {
      if (h) {
        const opt = document.createElement('option');
        opt.value = h;
        opt.textContent = h;
        columnSelect.appendChild(opt);
      }
    });

    columnGroup.classList.remove('hidden');
    startBtn.classList.remove('hidden');
    startBtn.disabled = !columnSelect.value;
  }

  columnSelect.addEventListener('change', () => {
    startBtn.disabled = !columnSelect.value;
  });

  // Start Job
  startBtn.addEventListener('click', async () => {
    if (!selectedFile || !columnSelect.value) return;

    showSection(progressSection);
    updateProgress('pending');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('category_column', columnSelect.value);

    try {
      const res = await fetch('/api/v1/upload', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      currentJobId = data.job_id;
      startPolling(currentJobId);

    } catch (err) {
      showError(err.message);
    }
  });

  function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/job/${jobId}`);
        if (!res.ok) return;

        const data = await res.json();
        const status = data.status;

        updateProgress(status);

        if (status === 'completed') {
          clearInterval(pollInterval);
          loadResults(jobId);
        } else if (status === 'failed') {
          clearInterval(pollInterval);
          showError(data.error_message || 'Pipeline processing failed.');
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 1200);
  }

  function updateProgress(status) {
    statusBadge.textContent = status;
    const pct = stageProgressMap[status] || 0;
    progressBarFill.style.width = `${pct}%`;

    let activeReached = false;
    steps.forEach(step => {
      const stage = step.dataset.stage;
      if (stage === status) {
        step.classList.add('active');
        step.classList.remove('completed');
        activeReached = true;
      } else if (!activeReached) {
        step.classList.add('completed');
        step.classList.remove('active');
      } else {
        step.classList.remove('active', 'completed');
      }
    });
  }

  async function loadResults(jobId) {
    try {
      const res = await fetch(`/api/v1/job/${jobId}/files`);
      if (!res.ok) throw new Error('Failed to load manifest.json');

      const manifest = await res.json();

      consolidationStat.textContent = manifest.taxonomy_summary;
      metricTotalRows.textContent = manifest.total_exported_rows.toLocaleString();
      metricUniqueCategories.textContent = manifest.total_unique_categories.toLocaleString();
      metricTotalGroups.textContent = manifest.total_groups.toLocaleString();

      downloadBtn.href = `/api/v1/download/${jobId}`;

      summaryTableBody.innerHTML = '';
      manifest.groups.forEach((g, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${idx + 1}</td>
          <td><strong>${escapeHtml(g.group_name)}</strong></td>
          <td><code>${escapeHtml(g.filename)}</code></td>
          <td>${g.row_count.toLocaleString()}</td>
        `;
        summaryTableBody.appendChild(tr);
      });

      showSection(resultsSection);

    } catch (err) {
      showError(err.message);
    }
  }

  function showError(msg) {
    if (pollInterval) clearInterval(pollInterval);
    errorMessageText.textContent = msg;
    showSection(errorSection);
  }

  function showSection(section) {
    [uploadSection, progressSection, resultsSection, errorSection].forEach(s => s.classList.add('hidden'));
    section.classList.remove('hidden');
  }

  resetBtn.addEventListener('click', () => {
    selectedFile = null;
    currentJobId = null;
    fileInput.value = '';
    fileDetails.classList.add('hidden');
    columnGroup.classList.add('hidden');
    startBtn.classList.add('hidden');
    showSection(uploadSection);
  });

  retryBtn.addEventListener('click', () => {
    showSection(uploadSection);
  });

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
});
