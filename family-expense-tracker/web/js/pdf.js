// jsPDF comes from the vendored UMD bundle loaded in index.html (window.jspdf).
const { jsPDF } = window.jspdf || {};

const MAX_EDGE = 2000; // cap long edge to keep files (and vision token cost) reasonable

// Decode any image the phone camera produces (incl. HEIC on Safari) into a
// downscaled JPEG on a canvas. Returns { jpegBlob, dataUrl, width, height }.
export async function normalizeImage(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // Fallback via <img> for browsers where createImageBitmap can't decode the type.
    bitmap = await loadViaImg(file);
  }
  let { width, height } = bitmap;
  const scale = Math.min(1, MAX_EDGE / Math.max(width, height));
  width = Math.round(width * scale);
  height = Math.round(height * scale);

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(bitmap, 0, 0, width, height);
  if (bitmap.close) bitmap.close();

  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
  const jpegBlob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.9));
  return { jpegBlob, dataUrl, width, height };
}

function loadViaImg(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}

// Wrap a normalized image into a single-page PDF sized to the photo.
export function imageToPdf(dataUrl, width, height) {
  const orientation = width >= height ? 'l' : 'p';
  const pdf = new jsPDF({ orientation, unit: 'px', format: [width, height] });
  pdf.addImage(dataUrl, 'JPEG', 0, 0, width, height);
  return pdf.output('blob');
}
