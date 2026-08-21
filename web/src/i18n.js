// Bilingual public surface. No i18n library: the build is offline and this is
// two languages over about sixty strings, which a dependency would not make
// smaller or clearer.
//
// The console stays English. It is an internal instrument for one office, and a
// half-translated enforcement screen is worse than an untranslated one -- an
// officer reading a case file needs the same wording that is printed on it.

import { useCallback, useEffect, useState } from 'react'

const KEY = 'pmr.lang'

export const LANGS = [
  { id: 'en', label: 'English' },
  { id: 'ta', label: 'தமிழ்' },   // தமிழ்
]

const S = {
  en: {
    office: 'Office of the District Supply Officer',
    district: 'Vellore District · Tamil Nadu',
    title: 'FairMark',
    lede: 'Check what vegetables and fruit sold for in the district today, or tell us what you were charged.',

    seePrices: "See today's prices",
    reportPrice: 'Report a price',
    seePricesSub: 'Wholesale rates from the district markets, updated daily.',
    reportPriceSub: 'Charged more than you expected? Take a minute to tell us.',

    statObservations: 'Prices checked',
    statLocations: 'Markets watched',
    statFlagged: 'Under investigation',

    caveat: 'This service flags price patterns for officers to investigate. It does not decide that anyone has broken the law, and it never names a shop or a trader.',
    dataThrough: 'Data through',

    // prices
    eggsNote: 'The declared rate is suggestive, not mandatory. Shops add their own margin, so a higher shop price is normal.',
    autosNote: 'The notified fare is the regulated rate for the distance. Waiting time and night trips are charged extra.',
    eggsTitle: 'Eggs',
    eggsDeclared: 'Declared rate',
    eggsShops: 'What shops charge',
    autosTitle: 'Autorickshaw fares',
    autosNotified: 'Notified fare',
    autosPaid: 'What riders report paying',
    distance: 'Distance',
    perPiece: 'per egg',
    commoditiesTitle: 'Vegetables and fruit',
    notEnough: 'not enough reports yet',
    pricesTitle: "Today's prices",
    pricesNote: 'What things cost in the district today, against the published rate where there is one.',
    commoditiesNote: 'What each item sold for across the district markets today, per kilo. These are wholesale market rates — shop prices are normally higher.',
    findItem: 'Find an item',
    commodity: 'Item',
    lowest: 'Lowest',
    typical: 'Typical',
    highest: 'Highest',
    mandis: 'Markets',
    noMatch: 'Nothing matches',
    pricesSource: 'Source: Agmarknet daily market prices, Government of India. An item is listed only when at least 3 markets reported it.',
    loading: 'Loading…',
    unavailable: 'Prices are unavailable right now.',
    back: 'Back',
    rpUnreachable: 'Could not reach the service. Your report was kept on this device.',

    // report form
    rpTitle: 'Report a price',
    rpWhat: 'What were you charged?',
    rpItem: 'Item',
    rpPricePaid: 'Price paid',
    unitPerKg: '\u20b9 per kg',
    unitPerPiece: '\u20b9 per egg',
    unitPerRide: '\u20b9 for the trip',
    rpDistance: 'Trip distance (km)',
    rpWhere: 'Where',
    rpUseLocation: 'Use my exact location',
    rpLocating: 'Locating…',
    rpTryAgain: 'Try location again',
    rpUseArea: 'Use the area instead',
    rpCaptured: 'Location captured.',
    rpFiledAgainst: 'filed against',
    rpNote: 'Note (optional)',
    rpNotePlaceholder: 'e.g. roadside shop, evening',
    rpSubmit: 'Submit report',
    rpSubmitting: 'Submitting…',
    rpPriceError: 'Enter a price above zero.',
    rpReference: 'Your reference',
    rpRecorded: 'Recorded. Your location is stored as a ~50m square, never an address.',
    rpQuoteRef: 'Quote this reference if you contact the district office about it.',
    rpRecordedAs: 'Recorded as',
    rpGridNote: 'Your coordinates will be rounded to a ~50m grid before anything is published — the record identifies a location, never a trader.',

    rpHappens: 'What happens to this',
    rpStep1: 'Recorded as the lowest evidence weight the system has.',
    rpStep2: 'Rejected outright if it lacks a location or a time.',
    rpStep3: 'Compared against the published rate for that item and area.',
    rpStep4: 'Reports close together quoting the same price count as one place, so repeat reports from one spot do not add weight.',
    rpStep5: 'A pattern built only from public reports needs three independent places before an officer is sent. Below that it is withheld.',
    rpOneReport: 'One report does not flag anyone. It is one observation among thousands.',

    rpSubmittedHere: 'Submitted from this device',
    rpNothingYet: 'Nothing submitted yet.',
    rpDownload: 'Download my reports (CSV)',
    rpSentOnline: 'Sent to the district office for review. This copy is yours.',
    rpOffline: 'Offline — reports stay on this device for now.',

    geoIdle: 'Optional. A precise location makes your report count for more.',
    geoLocating: 'Waiting for a position fix…',
    geoDenied: 'Location permission is blocked. Allow it in your browser settings, or just pick the area below.',
    geoTimeout: 'Could not get a fix in time. Try again, or pick the area below.',
    geoUnavailable: 'Your device could not provide a position. Pick the area below.',
    geoInsecure: 'Location needs a secure connection (https). Pick the area below.',
    geoOutside: 'You appear to be outside the covered district.',
    geoOutsideKm: 'You appear to be {km} km from the nearest covered market ({place}). This service covers Vellore district only — pick an area below if you are reporting on its behalf.',
  },
  ta: {
    office: 'மாவட்ட வழங்கல் அலுவலர் அலுவலகம்',
    district: 'வேலூர் மாவட்டம் · தமிழ்நாடு',
    title: 'FairMark',
    lede: 'மாவட்டத்தில் இன்று காய்கறி மற்றும் பழங்களின் விலையைப் பார்க்கவும், அல்லது நீங்கள் கொடுத்த விலையைத் தெரிவிக்கவும்.',

    seePrices: 'இன்றைய விலைகள்',
    reportPrice: 'விலையைத் தெரிவிக்க',
    seePricesSub: 'மாவட்ட சந்தைகளின் மொத்த விலைகள், தினம் புதுப்பிக்கப்படுகிறது.',
    reportPriceSub: 'எதிர்பார்த்ததை விட அதிக விலை வாங்கினார்களா? ஒரு நிமிடத்தில் தெரிவியுங்கள்.',

    statObservations: 'சரிபார்க்கப்பட்ட விலைகள்',
    statLocations: 'கண்காணிக்கும் சந்தைகள்',
    statFlagged: 'விசாரணையில் உள்ளது',

    caveat: 'இந்தச் சேவை விலை மாதிரிகளை அதிகாரிகள் விசாரிக்கப் பரிந்துரைக்கிறது. யாரேனும் சட்டத்தை மீறினார் என்று இது தீர்மானிக்கவில்லை; எந்த ஒரு கடையையோ வியாபாரியையோ இது பெயரிடுவதே இல்லை.',
    dataThrough: 'தரவு நாள்',

    eggsNote: 'அறிவிக்கப்பட்ட விலை பரிந்துரை மட்டுமே, கட்டாயம் அல்ல. கடைகள் தங்கள் லாபத்தைச் சேர்ப்பதால், சற்று அதிக விலை வழக்கமானதே.',
    autosNote: 'அரசு நிர்ணயித்த கட்டணமே அந்தத் தூரத்திற்கான முறையான கட்டணம். காத்திருப்பு நேரம் மற்றும் இரவுப் பயணங்களுக்குக் கூடுதல் கட்டணம் உண்டு.',
    eggsTitle: 'முட்டை',
    eggsDeclared: 'அறிவிக்கப்பட்ட விலை',
    eggsShops: 'கடைகளில் வசூலிக்கும் விலை',
    autosTitle: 'ஆட்டோ கட்டணம்',
    autosNotified: 'அரசு நிர்ணயித்த கட்டணம்',
    autosPaid: 'பயணிகள் தெரிவித்த கட்டணம்',
    distance: 'தூரம்',
    perPiece: 'ஒரு முட்டைக்கு',
    commoditiesTitle: 'காய்கறி மற்றும் பழங்கள்',
    notEnough: 'போதுமான தகவல்கள் இல்லை',
    pricesTitle: 'இன்றைய விலைகள்',
    pricesNote: 'இன்று மாவட்டத்தில் பொருட்களின் விலை, அறிவிக்கப்பட்ட விலையுடன் ஒப்பிட்டு.',
    commoditiesNote: 'இன்று மாவட்டச் சந்தைகளில் ஒரு கிலோவுக்கு விற்பனையான விலை. இவை மொத்த விலைகள் — கடை விலைகள் பொதுவாக அதிகமாக இருக்கும்.',
    findItem: 'பொருளைத் தேடுங்கள்',
    commodity: 'பொருள்',
    lowest: 'குறைந்தது',
    typical: 'வழக்கமானது',
    highest: 'அதிகபட்சம்',
    mandis: 'சந்தைகள்',
    noMatch: 'எதுவும் பொருந்தவில்லை',
    pricesSource: 'மூலம்: அக்மார்க்கெட் தினசரி சந்தை விலைகள், இந்திய அரசு. குறைந்தது 3 சந்தைகள் தெரிவித்தால் மாத்திரமே ஒரு பொருள் பட்டியலிடப்படுகிறது.',
    loading: 'ஏற்றுகிறது…',
    unavailable: 'விலைகள் தற்போது கிடைக்கவில்லை.',
    back: 'பின்',
    rpUnreachable: 'சேவையைத் தொடர்பு கொள்ள முடியவில்லை. உங்கள் தகவல் இந்தச் சாதனத்தில் சேமிக்கப்பட்டுள்ளது.',

    // report form
    rpTitle: 'விலையைத் தெரிவிக்க',
    rpWhat: 'எவ்வளவு கொடுத்தீர்கள்?',
    rpItem: 'பொருள்',
    rpPricePaid: 'கொடுத்த விலை',
    unitPerKg: '\u20b9 ஒரு கிலோவுக்கு',
    unitPerPiece: '\u20b9 ஒரு முட்டைக்கு',
    unitPerRide: '\u20b9 பயணத்திற்கு',
    rpDistance: 'பயண தூரம் (கி.மீ.)',
    rpWhere: 'எங்கே',
    rpUseLocation: 'என் இருப்பிடத்தைப் பயன்படுத்து',
    rpLocating: 'இருப்பிடம் தேடுகிறது…',
    rpTryAgain: 'மீண்டும் முயற்சிக்க',
    rpUseArea: 'பகுதியைத் தேர்ந்தெடுக்க',
    rpCaptured: 'இருப்பிடம் பதிவானது.',
    rpFiledAgainst: 'இதற்குப் பதிவு',
    rpNote: 'குறிப்பு (விருப்பம்)',
    rpNotePlaceholder: 'எ.கா. சாலையோரக் கடை, மாலை',
    rpSubmit: 'தெரிவிக்க',
    rpSubmitting: 'அனுப்புகிறது…',
    rpPriceError: 'பூஜ்ஜியத்திற்கு மேல் விலையை உள்ளிடவும்.',
    rpReference: 'உங்கள் குறிப்பு எண்',
    rpRecorded: 'பதிவானது. உங்கள் இருப்பிடம் சுமார் 50 மீட்டர் சதுரமாகச் சேமிக்கப்படுகிறது, முகவரியாக அல்ல.',
    rpQuoteRef: 'மாவட்ட அலுவலகத்தைத் தொடர்பு கொள்ளும்போது இந்த எண்ணைக் குறிப்பிடவும்.',
    rpRecordedAs: 'பதிவு செய்யப்பட்ட விதம்',
    rpGridNote: 'வெளியிடுவதற்கு முன் உங்கள் இருப்பிடம் சுமார் 50 மீட்டர் கட்டமாக மாற்றப்படும் — பதிவு ஓர் இடத்தைக் குறிக்கிறது, ஒருபோதும் ஒரு வியாபாரியை அல்ல.',

    rpHappens: 'இதற்கு அடுத்து என்ன',
    rpStep1: 'அமைப்பில் உள்ள மிகக் குறைந்த சான்று எடையுடன் பதிவு செய்யப்படும்.',
    rpStep2: 'இருப்பிடமோ நேரமோ இல்லாவிட்டால் நிராகரிக்கப்படும்.',
    rpStep3: 'அந்தப் பொருளுக்கும் பகுதிக்கும் அறிவிக்கப்பட்ட விலையுடன் ஒப்பிடப்படும்.',
    rpStep4: 'ஒரே விலையைத் தெரிவிக்கும் அருகருகே உள்ள தகவல்கள் ஓர் இடமாகவே கணக்கிடப்படும்; எனவே ஒரே இடத்திலிருந்து மீண்டும் தெரிவிப்பது கூடுதல் எடை சேர்க்காது.',
    rpStep5: 'பொதுமக்கள் தகவல்களை மட்டும் கொண்ட ஒரு மாதிரிக்கு, அதிகாரி அனுப்பப்படுவதற்கு முன் மூன்று தனித்தனி இடங்கள் தேவை. அதற்குக் குறைவாக இருந்தால் அது வெளியிடப்படாது.',
    rpOneReport: 'ஒரு தகவல் யாரையும் குற்றம் சாட்டாது. இது ஆயிரக்கணக்கான பதிவுகளில் ஒன்று.',

    rpSubmittedHere: 'இந்தச் சாதனத்திலிருந்து அனுப்பியவை',
    rpNothingYet: 'இதுவரை எதுவும் அனுப்பப்படவில்லை.',
    rpDownload: 'என் தகவல்களைப் பதிவிறக்க (CSV)',
    rpSentOnline: 'மாவட்ட அலுவலகத்திற்கு அனுப்பப்பட்டது. இந்த நகல் உங்களுடையது.',
    rpOffline: 'இணைப்பு இல்லை — தகவல்கள் தற்போது இந்தச் சாதனத்திலேயே இருக்கும்.',

    geoIdle: 'விருப்பம். துல்லியமான இருப்பிடம் உங்கள் தகவலுக்கு அதிக மதிப்பு சேர்க்கும்.',
    geoLocating: 'இருப்பிடத்திற்குக் காத்திருக்கிறது…',
    geoDenied: 'இருப்பிட அனுமதி தடுக்கப்பட்டுள்ளது. உலாவி அமைப்புகளில் அனுமதிக்கவும், அல்லது கீழே பகுதியைத் தேர்ந்தெடுக்கவும்.',
    geoTimeout: 'சரியான நேரத்தில் இருப்பிடம் கிடைக்கவில்லை. மீண்டும் முயற்சிக்கவும், அல்லது கீழே பகுதியைத் தேர்ந்தெடுக்கவும்.',
    geoUnavailable: 'உங்கள் சாதனத்தால் இருப்பிடத்தை வழங்க முடியவில்லை. கீழே பகுதியைத் தேர்ந்தெடுக்கவும்.',
    geoInsecure: 'இருப்பிடத்திற்குப் பாதுகாப்பான இணைப்பு (https) தேவை. கீழே பகுதியைத் தேர்ந்தெடுக்கவும்.',
    geoOutside: 'நீங்கள் இச்சேவை உள்ளடக்கிய மாவட்டத்திற்கு வெளியே இருப்பதாகத் தெரிகிறது.',
    geoOutsideKm: 'அருகிலுள்ள சந்தையிலிருந்து ({place}) நீங்கள் {km} கி.மீ. தொலைவில் இருப்பதாகத் தெரிகிறது. இச்சேவை வேலூர் மாவட்டத்தை மட்டுமே உள்ளடக்கியது — வேறு இடத்திற்காகத் தெரிவித்தால் கீழே ஒரு பகுதியைத் தேர்ந்தெடுக்கவும்.',
  },
}

export function useLang() {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem(KEY) || 'en' } catch { return 'en' }
  })
  useEffect(() => {
    try { localStorage.setItem(KEY, lang) } catch { /* private mode */ }
    document.documentElement.lang = lang
  }, [lang])
  // `vars` fills {name} placeholders. Only two strings need it, but building
  // them by concatenation would put a fragment of Tamil sentence structure into
  // JSX, where a translator cannot see or reorder it.
  const t = useCallback((k, vars) => {
    let out = (S[lang] && S[lang][k]) || S.en[k] || k
    if (vars) for (const [n, v] of Object.entries(vars)) out = out.split(`{${n}}`).join(v)
    return out
  }, [lang])
  return { lang, setLang, t }
}
