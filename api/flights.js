module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    const { lat = 30.0, lon = 50.0, dist = 1000 } = req.query;

    const roundedLat = parseFloat(lat).toFixed(1);
    const roundedLon = parseFloat(lon).toFixed(1);
    // محدود کردن حداکثر شعاع به ۱۵۰۰ کیلومتر جهت جلوگیری از بلاک شدن توسط API
    const safeDist = Math.min(parseInt(dist) || 1000, 1500);

    // لیست آدرس‌های API مرجع (اصلی و بک‌آپ)
    const endpoints = [
        `https://api.adsb.lol/v2/lat/${roundedLat}/lon/${roundedLon}/dist/${safeDist}`,
        `https://reapi.adsb.lol/v2/lat/${roundedLat}/lon/${roundedLon}/dist/${safeDist}`
    ];

    for (const url of endpoints) {
        try {
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'SkyRadarTracker/1.0 (Contact: sikjapid@gmail.com)',
                    'Accept': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                // کش ۱۰ ثانیه‌ای روی CDN ورسل برای کاهش فشار روی API
                res.setHeader('Cache-Control', 'public, s-maxage=10, stale-while-revalidate=15');
                return res.status(200).json(data);
            }
        } catch (err) {
            // رفتن به لینک بعدی در صورت خطا
            continue;
        }
    }

    // اگر تمام Endpointها پاسخ ندادند یا Rate Limit بودند
    return res.status(420).json({ error: 'Rate limit active on source servers' });
};
