import { ShieldCheck, Users, WalletCards, Building2, FileSearch, Headphones, Languages, QrCode } from 'lucide-react';

export const brandName = 'CHOWDARYS ONLINE SERVICES';
export const productName = 'DIGITAL DOCUMENT VAULT PRO';

export const roles = ['MASTER_SUPER_ADMIN', 'SUPER_ADMIN', 'ADMIN', 'OPERATOR', 'USER'] as const;
export const userStatuses = ['Pending', 'Active', 'Rejected', 'Suspended', 'On Hold'];
export const documentStatuses = ['Pending', 'Approved', 'Rejected', 'On Hold'];
export const requestStatuses = ['Pending', 'In Review', 'Uploaded', 'Completed', 'Rejected'];
export const ticketStatuses = ['Open', 'In Progress', 'Waiting', 'Resolved', 'Closed'];
export const languages = ['English', 'Telugu', 'Hindi', 'Tamil', 'Kannada'];

export const documentCategories = [
  'Aadhaar', 'e-Aadhaar', 'PAN', 'e-PAN', 'Voter ID', 'Passport', 'Driving License', 'ABHA Card',
  'Ayushman Card', 'PM Kisan Documents', 'Farmer Records', 'Ration Card', 'Income Certificate',
  'Caste Certificate', 'Residence Certificate', 'Birth Certificate', 'Death Certificate',
  'Educational Certificates', 'Insurance Documents', 'Land Records', 'Pension Documents',
  'Bank Documents', 'Utility Bills', 'Custom Document'
];

export const modules = [
  { title: 'Secure Family Vault', icon: ShieldCheck, text: 'Encrypted storage, family members, consent records, device tracking and signed URLs.' },
  { title: 'Customer CRM', icon: Users, text: 'Customer profiles, notes, tags, service history, follow-ups and login analytics.' },
  { title: 'Payments & Wallet', icon: WalletCards, text: 'UPI IDs, per-category download prices, wallet ledger, subscriptions and limits.' },
  { title: 'Franchise & White Label', icon: Building2, text: 'Unlimited brands, domains, themes, franchise hierarchy and revenue sharing.' },
  { title: 'OCR & AI Search', icon: FileSearch, text: 'OCR text, smart classification, duplicate detection, quality checks and extracted fields.' },
  { title: 'Service Center', icon: Headphones, text: 'Document requests, service requests and support tickets with workflow tracking.' },
  { title: 'Multi Language', icon: Languages, text: 'English, Telugu, Hindi, Tamil and Kannada-ready content architecture.' },
  { title: 'QR Verification', icon: QrCode, text: 'Customer, registration and document verification QR codes with verification IDs.' }
];

export const metrics = [
  ['Total Users', '128K+'], ['Total Documents', '4.8M+'], ['Revenue', '₹92.4L'], ['Downloads', '860K'],
  ['Storage Usage', '128 TB'], ['Active Users', '31K'], ['Pending Approvals', '436'], ['Pending Tickets', '82']
];
