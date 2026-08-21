// Tamil names for the commodities that appear in the daily price list.
//
// Keyed on the canonical item id, not the English label: the label is whatever
// Agmarknet printed that day ("Bhindi(Ladies Finger)", "Cucumbar(Kheera)") and
// its punctuation is not stable, whereas the id is derived and fixed.
//
// Anything not listed falls back to the English label rather than showing a
// transliteration nobody uses. A missing name is better than a wrong one, and
// the list is meant to grow.
//
// TRANSLATION CHECK: these were written without a native reviewer. They are
// the common market names rather than botanical ones, which is right for a
// shopper, but have a Tamil speaker read the list before the demo -- especially
// the three noted below where two English entries share one everyday Tamil word.
export const ITEMS_TA = {
  amaranthus: 'கீரை',
  apple: 'ஆப்பிள்',
  ashgourd: 'நீர்ப்பூசணிக்காய்',
  banana: 'வாழைப்பழம்',
  banana_green: 'வாழைக்காய்',
  beans: 'பீன்ஸ்',
  beetroot: 'பீட்ரூட்',
  bhindi_ladies_finger: 'வெண்டைக்காய்',
  bitter_gourd: 'பாகற்காய்',
  bottle_gourd: 'சுரைக்காய்',
  brinjal: 'கத்தரிக்காய்',
  cabbage: 'முட்டைக்கோஸ்',
  capsicum: 'குடைமிளகாய்',
  carrot: 'கேரட்',
  cauliflower: 'காலிஃபிளவர்',
  chow_chow: 'சௌ சௌ',
  cluster_beans: 'கொத்தவரங்காய்',
  coconut: 'தேங்காய்',
  colacasia: 'சேப்பங்கிழங்கு',
  coriander_leaves: 'கொத்தமல்லி',
  cowpea_veg: 'காராமணி',
  cucumbar_kheera: 'வெள்ளரிக்காய்',
  custard_apple_sharifa: 'சீதாப்பழம்',
  drumstick: 'முருங்கைக்காய்',
  elephant_yam_suran_amorphophallus: 'கருணைக்கிழங்கு',
  garlic: 'பூண்டு',
  ginger_green: 'இஞ்சி',
  green_avare_w: 'பச்சை அவரைக்காய்',      // shares "அவரை" with indian_beans_seam
  green_chilli: 'பச்சை மிளகாய்',
  groundnut: 'நிலக்கடலை',
  guava: 'கொய்யாப்பழம்',
  indian_beans_seam: 'மொச்சைக்காய்',       // shares "அவரை" with green_avare_w
  knool_khol: 'நூல்கோல்',
  lemon: 'எலுமிச்சை',
  mango: 'மாம்பழம்',
  mango_raw_ripe: 'மாங்காய்',
  marigold_calcutta: 'சாமந்திப்பூ',
  mint_pudina: 'புதினா',
  onion: 'வெங்காயம்',
  onion_green: 'வெங்காயத்தாள்',
  papaya: 'பப்பாளி',
  potato: 'உருளைக்கிழங்கு',
  pumpkin: 'பரங்கிக்காய்',
  raddish: 'முள்ளங்கி',
  ridgeguard_tori: 'பீர்க்கங்காய்',
  rose_local: 'ரோஜா',
  snakeguard: 'புடலங்காய்',
  sweet_corn: 'இனிப்பு சோளம்',
  sweet_potato: 'சர்க்கரைவள்ளிக்கிழங்கு',
  tender_coconut: 'இளநீர்',
  thondekai: 'கோவைக்காய்',
  tomato: 'தக்காளி',
  yam_ratalu: 'வள்ளிக்கிழங்கு',           // shares "கிழங்கு" with sweet_potato

  egg_table: 'முட்டை',
  auto_ride: 'ஆட்டோ கட்டணம்',
}
