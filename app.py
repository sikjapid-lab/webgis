/* =========================================================
   7d-3) ردیابی زنده پرواز (ADS-B — OpenSky Network با احراز هویت OAuth2)
   ========================================================= */

// مدیریت کش توکن دسترسی OAuth2
let openskyAccessToken = null;
let openskyTokenExpiry = 0;

/**
 * دریافت و مدیریت توکن OAuth2 از سرور OpenSky Network
 */
async function getOpenSkyAccessToken() {
  const now = Date.now();
  // اگر توکن موجود و همچنان معتبر باشد (با ۵ دقیقه هامش اطمینان)، از توکن کش‌شده استفاده کن
  if (openskyAccessToken && now < openskyTokenExpiry - 300000) {
    return openskyAccessToken;
  }

  const clientId = CONFIG.OPENSKY_CLIENT_ID || 'sikjapid@gmail.com-api-client';
  const clientSecret = CONFIG.OPENSKY_CLIENT_SECRET || '2lzjHSo5FaXLt6fJ9SyweYKiAtW0uZN2';

  const targetAuthUrl = 'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token';
  // استفاده از پروکسی CORS برای عبور از محدودیت مرورگر
  const proxyAuthUrl = 'https://corsproxy.io/?' + encodeURIComponent(targetAuthUrl);

  const bodyParams = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: clientId,
    client_secret: clientSecret
  });

  const res = await fetch(proxyAuthUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: bodyParams
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error('خطا در دریافت توکن OAuth2 OpenSky (' + res.status + '): ' + errBody);
  }

  const data = await res.json();
  openskyAccessToken = data.access_token;
  // محاسبه زمان انقضا (تبدیل به میلی‌ثانیه)
  openskyTokenExpiry = now + ((data.expires_in || 1800) * 1000);
  return openskyAccessToken;
}

function altitudeColor(altM){
  if (altM == null || altM < 0) return '#8a8a8a';       // روی زمین / نامشخص
  if (altM < 1000)  return '#8a8a8a';
  if (altM < 3000)  return '#3aa0ff';
  if (altM < 6000)  return '#2dd4e8';
  if (altM < 9000)  return '#4bd07a';
  if (altM < 11000) return '#f5c542';
  return '#f5a623';
}

function planeDivIcon(color, headingDeg){
  const rot = (headingDeg || 0);
  return L.divIcon({
    className:'flight-icon',
    html:'<svg width="22" height="22" viewBox="0 0 24 24" style="transform:rotate('+rot+'deg)"><path d="M12 2 L15 10 L22 13 L15 15 L16 21 L12 19 L8 21 L9 15 L2 13 L9 10 Z" fill="'+color+'" stroke="#0a0f14" stroke-width="0.8"/></svg>',
    iconSize:[22,22], iconAnchor:[11,11]
  });
}

let flightLeafletGroup = L.layerGroup();
let flightCesiumEntities = {};
let flightTimer = null;
let flightFetchInFlight = false;

async function fetchFlights(){
  if (flightFetchInFlight) return;
  if (!document.getElementById('ovFlights').checked) return;
  flightFetchInFlight = true;
  try{
    // ۱. دریافت توکن احراز هویت
    const token = await getOpenSkyAccessToken();

    // ۲. محاسبه محدوده دید نقشه
    const b = leafletMap.getBounds();
    const targetApiUrl = 'https://opensky-network.org/api/states/all?lamin='+b.getSouth()+'&lomin='+b.getWest()+'&lamax='+b.getNorth()+'&lomax='+b.getEast();
    
    // ۳. فراخوانی API از طریق پروکسی همراه با توکن Authorization Bearer
    const proxyApiUrl = 'https://corsproxy.io/?' + encodeURIComponent(targetApiUrl);
    const res = await fetch(proxyApiUrl, {
      headers: {
        'Authorization': 'Bearer ' + token
      }
    });

    if (!res.ok) throw new Error('HTTP '+res.status);
    const data = await res.json();
    const states = data.states || [];

    // ۴. پاکسازی لایه‌های قبلی
    leafletMap.removeLayer(flightLeafletGroup);
    flightLeafletGroup.clearLayers();
    Object.values(flightCesiumEntities).forEach(ent=>cesiumViewer.entities.remove(ent));
    flightCesiumEntities = {};

    // ۵. رندر کردن موقعیت پروازها روی ۲بعدی و ۳بعدی
    states.forEach(s=>{
      const [icao24, callsign, originCountry, , , lon, lat, baroAlt, onGround, velocity, trueTrack, , , geoAlt] = s;
      if (lat == null || lon == null) return;
      const alt = geoAlt != null ? geoAlt : baroAlt;
      const color = onGround ? '#8a8a8a' : altitudeColor(alt);
      const label = (callsign || icao24 || '').trim();
      const icon = planeDivIcon(color, trueTrack);
      
      const popupHtml = '<b>'+escapeHtml(label || 'پرواز ناشناس')+'</b>'
        + '<div style="font-size:11px;color:#7f92a6;margin-top:4px">'
        + 'کشور: ' + escapeHtml(originCountry || 'نامشخص') + '<br>'
        + 'ارتفاع: '+(alt!=null? Math.round(alt)+' m':'—')
        + ' · سرعت: '+(velocity!=null? Math.round(velocity*3.6)+' km/h':'—')+'</div>'
        + (onGround ? '<div style="font-size:10.5px;color:#f5a623">روی زمین</div>' : '');
      
      // افزودن به نقشه Leaflet
      const m = L.marker([lat, lon], {icon}).bindPopup(popupHtml);
      flightLeafletGroup.addLayer(m);

      // افزودن به کره ۳بعدی Cesium
      const ent = cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(lon, lat, alt || 0),
        point: { pixelSize: 7, color: Cesium.Color.fromCssColorString(color), outlineColor: Cesium.Color.BLACK, outlineWidth: 1 },
        description: popupHtml
      });
      flightCesiumEntities[icao24] = ent;
    });

    flightLeafletGroup.addTo(leafletMap);
  }catch(err){
    console.error('خطا در دریافت داده OpenSky', err);
  }finally{
    flightFetchInFlight = false;
  }
}

function toggleFlights(on){
  if (on){
    fetchFlights();
    if (flightTimer) clearInterval(flightTimer);
    flightTimer = setInterval(fetchFlights, 10000); // به‌روزرسانی هر ۱۰ ثانیه با توجه به داشتن حساب کاربردی معتبر
  } else {
    if (flightTimer){ clearInterval(flightTimer); flightTimer = null; }
    leafletMap.removeLayer(flightLeafletGroup);
    flightLeafletGroup.clearLayers();
    Object.values(flightCesiumEntities).forEach(ent=>cesiumViewer.entities.remove(ent));
    flightCesiumEntities = {};
  }
}

document.getElementById('ovFlights').addEventListener('change', e=>toggleFlights(e.target.checked));

let flightMoveDebounce = null;
leafletMap.on('moveend', ()=>{
  if (!document.getElementById('ovFlights').checked) return;
  clearTimeout(flightMoveDebounce);
  flightMoveDebounce = setTimeout(fetchFlights, 1200);
});
