// Sample data for the interactive demo — mirrors the real app's seed-data
// style (Hotel Aryaas / Pro Max Demo Hotel, seen in the real screenshots)
// so the demo feels authentic. No connection to any real tenant.
const DEMO_HOTEL_NAME = "Hotel Aryaas (Demo)";
const DEMO_HOTEL_ADDR = "8/1, Bus Stand, Paramakudi, 623707";

const SECTIONS = [
  { id: "ac", name: "AC", seating: true },
  { id: "nonac", name: "Non-AC", seating: true },
  { id: "takeaway", name: "Takeaway", seating: false },
  { id: "online", name: "Online Delivery", seating: false },
];

const TABLES = [
  { id: "t1", number: "T1", sectionId: "ac", seats: 4 },
  { id: "t2", number: "T2", sectionId: "ac", seats: 4 },
  { id: "t3", number: "T3", sectionId: "ac", seats: 4 },
  { id: "t4", number: "T4", sectionId: "nonac", seats: 4 },
  { id: "t5", number: "T5", sectionId: "nonac", seats: 4 },
  { id: "t6", number: "T6", sectionId: "nonac", seats: 4 },
];

const CATEGORIES = ["Top Selling", "Tiffen", "Variety Rice", "Meals", "Beverages"];

// hue used for each item card's colored header block (no per-item photos in the demo)
const ITEMS = [
  { code: 17, name: "Dosai", nameTa: "தோசை", price: 60, category: "Tiffen", top: true, hue: 28 },
  { code: 61, name: "Vadai", nameTa: "வடை", price: 10, category: "Tiffen", top: true, hue: 40 },
  { code: 1, name: "Tea", nameTa: "டீ", price: 15, category: "Beverages", top: true, hue: 20 },
  { code: 2, name: "Filter Coffee", nameTa: "பில்டர் காபி", price: 30, category: "Beverages", top: true, hue: 15 },
  { code: 101, name: "Meals", nameTa: "சாப்பாடு", price: 110, category: "Meals", top: true, hue: 95 },
  { code: 103, name: "Chicken Biryani", nameTa: "சிக்கன் பிரியாணி", price: 220, category: "Variety Rice", top: true, hue: 10 },
  { code: 35, name: "Pongal", nameTa: "பொங்கல்", price: 60, category: "Tiffen", hue: 45 },
  { code: 20, name: "Poori", nameTa: "பூரி", price: 60, category: "Tiffen", hue: 35 },
  { code: 104, name: "Masala Dosa", nameTa: "மசாலா தோசை", price: 90, category: "Tiffen", hue: 25 },
  { code: 105, name: "Gulab Jamun", nameTa: "குலாப் ஜாமுன்", price: 60, category: "Meals", hue: 320 },
  { code: 83, name: "Curd Rice", nameTa: "தயிர் சாதம்", price: 50, category: "Variety Rice", hue: 55 },
  { code: 82, name: "Tomato Rice", nameTa: "தக்காளி சாதம்", price: 55, category: "Variety Rice", hue: 8 },
  { code: 102, name: "Parcel Meals", nameTa: "பார்சல் சாப்பாடு", price: 120, category: "Meals", hue: 100 },
  { code: 37, name: "Parotta", nameTa: "பரோட்டா", price: 15, category: "Tiffen", hue: 42 },
  { code: 152, name: "Water 1 Lt", nameTa: "தண்ணீர்", price: 20, category: "Beverages", hue: 200 },
  { id: 5, code: 7, name: "Driver Tea", nameTa: "டிரைவர் டீ", price: 10, category: "Beverages", hue: 22 },
];

function itemByCode(code) {
  return ITEMS.find((i) => i.code === Number(code));
}
function sectionById(id) {
  return SECTIONS.find((s) => s.id === id);
}
function tableById(id) {
  return TABLES.find((t) => t.id === id);
}
