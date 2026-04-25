export type MinistryFamily = 'agri' | 'finance' | 'health' | 'housing' | 'women' | 'msme' | 'rural' | 'default';

export interface CuratedScheme {
  id: string;
  name: string;
  emoji: string;
  summary: string;
  ministry: string;
  /** Optional — only the static curated entries below set this; dynamic API rows omit it. */
  ministryFamily?: MinistryFamily;
  benefit: string;
  eligibility: string;
  applyLink: string;
  sourceLink: string;
  /** Optional — same as above. Dynamic rows from /api/v2/featured don't ship a default role. */
  defaultRole?:
    | 'farmer'
    | 'woman'
    | 'student'
    | 'artisan'
    | 'senior citizen'
    | 'below poverty line household';
  /** Set on dynamic rows from /api/v2/featured so we can deep-link or fetch detail. */
  slug?: string;
  /** "central" | "state" — drives the small location pill on dynamic cards. */
  level?: string;
  /** State name when level="state"; absent for central schemes. */
  state?: string | null;
}

export const CURATED_SCHEMES: CuratedScheme[] = [
  {
    id: 'pm-kisan',
    name: 'PM Kisan',
    emoji: '🌾',
    summary: 'Income support of ₹6,000/year for farmers.',
    ministry: 'Ministry of Agriculture & Farmers Welfare',
    ministryFamily: 'agri',
    benefit: '₹6,000/year DBT income support for farmers.',
    eligibility: 'Landholding farmers as per state land records / PM-KISAN database.',
    applyLink: 'https://pmkisan.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pm-kisan',
    defaultRole: 'farmer',
  },
  {
    id: 'ayushman-bharat',
    name: 'Ayushman Bharat',
    emoji: '🏥',
    summary: 'Health cover of ₹5 Lakh per family.',
    ministry: 'Ministry of Health & Family Welfare',
    ministryFamily: 'health',
    benefit: '₹5 lakh/year family floater for secondary/tertiary care.',
    eligibility: 'Families identified as per SECC / state criteria for PM-JAY.',
    applyLink: 'https://pmjay.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pmjay',
    defaultRole: 'below poverty line household',
  },
  {
    id: 'pm-awas',
    name: 'PM Awas Yojana',
    emoji: '🏠',
    summary: 'Housing for all with financial assistance.',
    ministry: 'Ministry of Housing & Urban Affairs / Rural Development',
    ministryFamily: 'housing',
    benefit: 'Financial assistance & interest subsidy for pucca house.',
    eligibility: 'Economically weaker sections / LIG as per scheme component (urban/rural).',
    applyLink: 'https://pmaymis.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pmay-u',
    defaultRole: 'below poverty line household',
  },
  {
    id: 'sukanya-samriddhi',
    name: 'Sukanya Samriddhi',
    emoji: '👧',
    summary: 'High-interest savings for the girl child.',
    ministry: 'Ministry of Finance',
    ministryFamily: 'finance',
    benefit: 'Small savings with attractive interest & tax benefits for girl child.',
    eligibility: 'Girl child below 10 years; guardian can open account at authorised banks/post office.',
    applyLink: 'https://www.indiapost.gov.in/Financial/Pages/Content/SSY.aspx',
    sourceLink: 'https://www.myscheme.gov.in/schemes/sukanya-samriddhi-yojana',
    defaultRole: 'woman',
  },
  {
    id: 'pm-mudra',
    name: 'PM Mudra Yojana',
    emoji: '💰',
    summary: 'Loans for small business up to ₹10 Lakh.',
    ministry: 'MoMSME (through banks/NBFCs)',
    ministryFamily: 'msme',
    benefit: 'Collateral-free micro/small business loans up to ₹10 lakh (Shishu/Kishor/Tarun).',
    eligibility: 'Non-corporate small business / MSE units with documented business need.',
    applyLink: 'https://www.mudra.org.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pm-mudra-yojana',
    defaultRole: 'artisan',
  },
  {
    id: 'ujjwala',
    name: 'Ujjwala Yojana',
    emoji: '🔥',
    summary: 'Free LPG connections for BPL households.',
    ministry: 'Ministry of Petroleum & Natural Gas',
    ministryFamily: 'women',
    benefit: 'Free LPG connection & financial support for first refill & stove where applicable.',
    eligibility: 'Women adult members of poor households without LPG connection (BPL/AHL criteria).',
    applyLink: 'https://www.pmuy.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pm-ujjwala-yojana',
    defaultRole: 'woman',
  },
  {
    id: 'mgnrega',
    name: 'MGNREGA',
    emoji: '⚒️',
    summary: 'Guaranteed 100 days of rural employment.',
    ministry: 'Ministry of Rural Development',
    ministryFamily: 'rural',
    benefit: 'Up to 100 days of wage employment per rural household per FY.',
    eligibility: 'Adult members of rural households volunteering unskilled manual work.',
    applyLink: 'https://nrega.nic.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/mgnrega',
    defaultRole: 'farmer',
  },
  {
    id: 'pm-vishwakarma',
    name: 'PM Vishwakarma',
    emoji: '🔧',
    summary: 'Support for traditional artisans and crafts.',
    ministry: 'MoMSME',
    ministryFamily: 'msme',
    benefit: 'Toolkit incentive (₹15,000) and concessional loans for artisans/craftspeople.',
    eligibility: 'Traditional artisans in eligible trades registered on PM Vishwakarma portal.',
    applyLink: 'https://pmvishwakarma.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pm-vishwakarma',
    defaultRole: 'artisan',
  },
  {
    id: 'pm-svanidhi',
    name: 'PM SVANidhi',
    emoji: '🛒',
    summary: 'Working capital loans for street vendors.',
    ministry: 'Ministry of Housing & Urban Affairs',
    ministryFamily: 'housing',
    benefit: 'Collateral-free working capital loans for street vendors in urban areas.',
    eligibility: 'Street vendors identified through ULB surveys / certificate of vending.',
    applyLink: 'https://pmsvanidhi.mohua.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pm-svanidhi',
    defaultRole: 'artisan',
  },
  {
    id: 'gruha-lakshmi',
    name: 'Gruha Lakshmi',
    emoji: '🤱',
    summary: '₹2,000/month for women heads of families.',
    ministry: 'Government of Karnataka',
    ministryFamily: 'women',
    benefit: '₹2,000/month to eligible woman heads of households.',
    eligibility: 'Women heads meeting Karnataka residency & BPL/Antyodaya criteria as notified.',
    applyLink: 'https://ahara.kar.nic.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/gruha-lakshmi',
    defaultRole: 'woman',
  },
  {
    id: 'rythu-bharosa',
    name: 'Rythu Bharosa',
    emoji: '🚜',
    summary: '₹13,500/year support for AP farmers.',
    ministry: 'Government of Andhra Pradesh',
    ministryFamily: 'agri',
    benefit: '₹13,500/year support instalments for farmers & tenant cultivators.',
    eligibility: 'AP farmer families / cultivators as per state land & tenant verification.',
    applyLink: 'https://www.ap.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/ysr-rythu-bharosa',
    defaultRole: 'farmer',
  },
  {
    id: 'jan-dhan',
    name: 'Jan Dhan Yojana',
    emoji: '💳',
    summary: 'Zero balance savings accounts for all.',
    ministry: 'Ministry of Finance',
    ministryFamily: 'finance',
    benefit: 'Basic savings account, RuPay card, accident insurance & optional OD.',
    eligibility: 'Any Indian resident without a bank account (relaxed KYC / full KYC tiers).',
    applyLink: 'https://www.pmjdy.gov.in/',
    sourceLink: 'https://www.myscheme.gov.in/schemes/pradhan-mantri-jan-dhan-yojana-pmjdy',
    defaultRole: 'below poverty line household',
  },
];
