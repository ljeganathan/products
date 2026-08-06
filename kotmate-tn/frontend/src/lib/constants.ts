// Mirrors backend/app/core/constants.py INDIAN_STATES — kept in sync by hand since
// the list changes rarely (last Indian state/UT boundary change was 2019, J&K/Ladakh).
export const INDIAN_STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
] as const;

export const PLAN_LABELS: Record<string, string> = {
  lite: "Lite",
  pro: "Pro",
  pro_max: "Pro Max",
};

// Mirrors backend/app/core/constants.py GST_STATE_CODES — a GSTIN's first two digits
// are the numeric state/UT code, used to warn (not block) when it disagrees with the
// selected State (CLAUDE.md §9, Phase 10).
export const GST_STATE_CODES: Record<string, string> = {
  "01": "Jammu and Kashmir",
  "02": "Himachal Pradesh",
  "03": "Punjab",
  "04": "Chandigarh",
  "05": "Uttarakhand",
  "06": "Haryana",
  "07": "Delhi",
  "08": "Rajasthan",
  "09": "Uttar Pradesh",
  "10": "Bihar",
  "11": "Sikkim",
  "12": "Arunachal Pradesh",
  "13": "Nagaland",
  "14": "Manipur",
  "15": "Mizoram",
  "16": "Tripura",
  "17": "Meghalaya",
  "18": "Assam",
  "19": "West Bengal",
  "20": "Jharkhand",
  "21": "Odisha",
  "22": "Chhattisgarh",
  "23": "Madhya Pradesh",
  "24": "Gujarat",
  "26": "Dadra and Nagar Haveli and Daman and Diu",
  "27": "Maharashtra",
  "29": "Karnataka",
  "30": "Goa",
  "31": "Lakshadweep",
  "32": "Kerala",
  "33": "Tamil Nadu",
  "34": "Puducherry",
  "35": "Andaman and Nicobar Islands",
  "36": "Telangana",
  "37": "Andhra Pradesh",
  "38": "Ladakh",
};

export function gstinStateWarning(gstin: string, state: string): string | null {
  if (!gstin || gstin.length < 2 || !state) return null;
  const expected = GST_STATE_CODES[gstin.slice(0, 2)];
  if (!expected) return `GSTIN prefix '${gstin.slice(0, 2)}' isn't a recognized state/UT code — double-check the GSTIN.`;
  if (expected !== state) return `This GSTIN's state code suggests ${expected}, but ${state} is selected.`;
  return null;
}
