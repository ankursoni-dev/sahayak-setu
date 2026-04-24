"""Lightweight rule hints vs user profile — illustrative, not legal eligibility."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.services.retrieval_service import SearchResult


@dataclass(frozen=True)
class _Rule:
    pattern: str
    needs_woman: bool = False
    needs_business_intent: bool = False
    needs_farmer: bool = False
    needs_student: bool = False
    needs_elderly: bool = False
    needs_bpl: bool = False
    needs_worker: bool = False
    # Universal = True means virtually everyone qualifies; return likely_eligible by default
    universal: bool = False
    reason_ok: str = "Profile matches common scheme focus (heuristic)."
    reason_fail: str = "Rule hint: profile may not match typical scheme focus — verify on the official portal."


# ── signal detectors ────────────────────────────────────────────────────────

def _text_profile(profile: dict) -> str:
    parts: list[str] = []
    for k in ("gender", "occupation", "category", "state", "bpl"):
        v = profile.get(k)
        if v is None:
            continue
        parts.append(str(v).lower())
    return " ".join(parts)


def _has_woman(blob: str) -> bool:
    return bool(re.search(
        r"\b(woman|women|female|lady|ladies|girl|mahila|stree|nar[iı]|ladki|behna)\b",
        blob, re.I,
    ))


def _has_business(blob: str) -> bool:
    return bool(re.search(
        r"\b(business|startup|enterprise|msme|self[\s-]?employ|loan|udhyog|vyapar|dukan|shop|vendor|artisan|craft)\b",
        blob, re.I,
    ))


def _has_farmer(blob: str) -> bool:
    return bool(re.search(
        r"\b(farmer|kisan|agriculture|cultivat|crop|land|kheti|fasal|gramin)\b",
        blob, re.I,
    ))


def _has_student(blob: str) -> bool:
    return bool(re.search(
        r"\b(student|study|school|college|education|class|degree|diploma|scholarship|vidyarthi|padhai)\b",
        blob, re.I,
    ))


def _has_elderly(blob: str) -> bool:
    return bool(re.search(
        r"\b(senior|elderly|old\s*age|aged|retired|pension|60\s*year|65\s*year|70\s*year|budhapa|vriddh)\b",
        blob, re.I,
    ))


def _has_bpl(blob: str) -> bool:
    return bool(re.search(
        r"\b(bpl|below\s*poverty|ration\s*card|antyodaya|poor|garib|yojana\s*list)\b",
        blob, re.I,
    ))


def _has_worker(blob: str) -> bool:
    return bool(re.search(
        r"\b(worker|labour|labourer|unorganised|informal|daily\s*wage|migrant|mazdoor|shramik|construction|domestic)\b",
        blob, re.I,
    ))


# ── rules list ───────────────────────────────────────────────────────────────

_RULES: tuple[_Rule, ...] = (

    # ── Agriculture ──────────────────────────────────────────────────────────
    _Rule(
        r"pm[\s-]?kisan\s*(samman|nidhi)?$|pradhan\s*mantri\s*kisan",
        needs_farmer=True,
        reason_ok="PM-KISAN targets small/marginal farmers with cultivable land — your farmer profile aligns. Confirm land records (Khasra/Khatauni) are up to date.",
        reason_fail="PM-KISAN requires a farming household with landholding records. Mention farmer status or land ownership for eligibility.",
    ),
    _Rule(
        r"kisan\s*credit\s*card|kcc",
        needs_farmer=True,
        reason_ok="KCC provides crop credit to farmers and allied sector workers. Your farmer profile fits — apply at any bank with land documents.",
        reason_fail="KCC is for farmers, sharecroppers, and livestock/fisheries workers. Mention farming occupation for eligibility.",
    ),
    _Rule(
        r"pmfby|fasal\s*bima|crop\s*insurance",
        needs_farmer=True,
        reason_ok="PMFBY is for farmers growing notified crops — your farmer profile fits. Enrol before cut-off through your bank.",
        reason_fail="PMFBY is for farmers growing notified crops. Farmer/landholding status required.",
    ),
    _Rule(
        r"pm[\s-]?kusum|kusum\s*pump|solar\s*pump",
        needs_farmer=True,
        reason_ok="PM-KUSUM supports farmers replacing diesel/electric pumps with solar. Your farmer profile aligns — apply via state DISCOM.",
        reason_fail="PM-KUSUM is for agricultural landholders replacing pumps with solar. Farmer status required.",
    ),
    _Rule(
        r"pm[\s-]?k[my]\b|kisan\s*maandhan|kisan\s*pension",
        needs_farmer=True,
        reason_ok="PM-KMY is a pension scheme for small/marginal farmers aged 18–40. Your farmer profile fits.",
        reason_fail="PM-KMY is for small/marginal farmers (up to 2 hectares) aged 18–40. Farmer status required.",
    ),
    _Rule(
        r"pm[\s-]?aasha|msp|minimum\s*support\s*price",
        needs_farmer=True,
        reason_ok="PM-AASHA protects farmers from selling below MSP. Register with the state agriculture department before harvest.",
        reason_fail="PM-AASHA is for registered farmers selling notified crops.",
    ),
    _Rule(
        r"e[\s-]?nam|national\s*agriculture\s*market",
        needs_farmer=True,
        reason_ok="e-NAM is open to all registered farmers at connected mandis. Register with your mandi secretariat.",
        reason_fail="e-NAM requires farmer registration at a connected APMC mandi.",
    ),
    _Rule(
        r"soil\s*health|soil\s*card",
        needs_farmer=True,
        reason_ok="Soil Health Card is free for all farmers — submit a sample at the nearest KVK or soil testing lab.",
        reason_fail="Soil Health Card is for farmers with cultivable land.",
    ),
    _Rule(
        r"rkvy|rashtriya\s*krishi\s*vikas",
        needs_farmer=True,
        reason_ok="RKVY benefits farmers through state-level projects. Contact your district agriculture office.",
        reason_fail="RKVY is implemented at the state level primarily for farming communities.",
    ),
    _Rule(
        r"kisan\s*sampada|food\s*processing\s*enterprise",
        needs_business_intent=True,
        reason_ok="PM-Kisan Sampada supports food processing enterprises and FPOs. Your business profile aligns.",
        reason_fail="PM-Kisan Sampada is for food processing businesses, FPOs, and cooperatives.",
    ),
    _Rule(
        r"livestock|national\s*livestock",
        reason_ok="National Livestock Mission is open to farmers, SHGs, and FPOs in poultry, goat, and allied sectors. Apply at nlm.udyamimitra.in.",
        reason_fail="National Livestock Mission targets farmers and entrepreneurs in the livestock sector.",
    ),

    # ── Health ────────────────────────────────────────────────────────────────
    _Rule(
        r"ayushman\s*bharat|pm[\s-]?jay|pmjay",
        universal=True,
        reason_ok="Ayushman Bharat covers families listed in SECC 2011 or state list. Check your eligibility at pmjay.gov.in with Aadhaar.",
        reason_fail="Ayushman Bharat targets SECC 2011 listed families. Verify your name at pmjay.gov.in.",
    ),
    _Rule(
        r"ayushman\s*(card|bharat\s*card|jan\s*arogya\s*card)",
        universal=True,
        reason_ok="Ayushman Card can be generated free at beneficiary.nha.gov.in if your family is in the PMJAY list.",
        reason_fail="Ayushman Card requires SECC 2011 or state-added beneficiary status.",
    ),
    _Rule(
        r"ab[\s-]?hwc|health\s*wellness\s*cent",
        universal=True,
        reason_ok="Health and Wellness Centres provide free primary healthcare to all citizens. Visit your nearest HWC.",
        reason_fail="HWCs serve all citizens — no eligibility restriction.",
    ),
    _Rule(
        r"jan\s*aushadhi|aushadhi\s*kendra|generic\s*medicine",
        universal=True,
        reason_ok="Jan Aushadhi stores are open to all. Visit the nearest PMBJK store for medicines at 50–90% lower cost.",
        reason_fail="Jan Aushadhi stores are accessible to all citizens.",
    ),
    _Rule(
        r"nhm|national\s*health\s*mission",
        universal=True,
        reason_ok="NHM provides free OPD, medicines, and diagnostics at government health facilities for all citizens.",
        reason_fail="NHM services are available free to all at government health centres.",
    ),
    _Rule(
        r"mission\s*indradhanush|immunization|vaccination",
        universal=True,
        reason_ok="Mission Indradhanush is free for all children under 2 years and pregnant women. Visit the nearest PHC or ANM.",
        reason_fail="Mission Indradhanush targets unvaccinated/partially vaccinated children and pregnant women.",
    ),
    _Rule(
        r"jsy|janani\s*suraksha",
        needs_woman=True,
        needs_bpl=True,
        reason_ok="JSY gives cash incentive for institutional delivery to BPL pregnant women. Your profile fits — register at the nearest ANM.",
        reason_fail="JSY targets pregnant BPL women for institutional delivery incentives.",
    ),
    _Rule(
        r"national\s*ayush|ayurveda|yoga\s*wellness",
        universal=True,
        reason_ok="AYUSH services are free at government AYUSH hospitals and HWCs for all citizens.",
        reason_fail="National Ayush Mission services are available at government facilities.",
    ),
    _Rule(
        r"nikshay|tb\s*mukt|tuberculosis|pm\s*tb",
        universal=True,
        reason_ok="Nikshay Poshan gives Rs 500/month nutritional support to all registered TB patients. Visit any government DOTs centre.",
        reason_fail="Nikshay Poshan is for TB patients registered under RNTCP.",
    ),
    _Rule(
        r"poshan\s*abhiyan|nutrition\s*mission|anganwadi\s*nutrit",
        universal=True,
        reason_ok="POSHAN Abhiyan provides nutrition services to children under 6, pregnant/lactating mothers through Anganwadi Centres.",
        reason_fail="POSHAN Abhiyan targets children 0–6 years, pregnant and lactating mothers.",
    ),

    # ── Women & Children ──────────────────────────────────────────────────────
    _Rule(
        r"pmmvy|pm\s*matru\s*vandana|maternity\s*benefit",
        needs_woman=True,
        reason_ok="PMMVY gives Rs 5,000 for the first pregnancy. Your woman profile matches — apply at the nearest Anganwadi Centre.",
        reason_fail="PMMVY is for pregnant women (19+ years) for their first live birth.",
    ),
    _Rule(
        r"beti\s*bachao|beti\s*padhao|bbbp",
        needs_woman=True,
        reason_ok="BBBP supports girl children — open a Sukanya Samriddhi account at any post office for financial benefits.",
        reason_fail="BBBP primarily benefits girl children and their families.",
    ),
    _Rule(
        r"sukanya\s*samriddhi|ssy\b",
        needs_woman=True,
        reason_ok="SSY is for girl children (birth to 10 years) — open an account at a post office/bank with the girl's birth certificate.",
        reason_fail="SSY is exclusively for girl children from birth to 10 years of age.",
    ),
    _Rule(
        r"icds|anganwadi",
        universal=True,
        reason_ok="Anganwadi services are free for children under 6 and pregnant/lactating mothers. Register at your nearest Anganwadi Centre.",
        reason_fail="Anganwadi/ICDS services target children under 6 years and pregnant/lactating women.",
    ),
    _Rule(
        r"pm[\s-]?cares\s*for\s*children|covid\s*orphan",
        universal=True,
        reason_ok="PM-CARES for Children supports children who lost parents to COVID-19. Apply through the District Magistrate.",
        reason_fail="PM-CARES for Children is for children who lost parents/guardian to COVID-19 (March 2020 – Dec 2021).",
    ),

    # ── Housing ───────────────────────────────────────────────────────────────
    _Rule(
        r"pmay[\s-]?u|pm\s*awas.*urban|housing.*urban",
        reason_ok="PMAY-U provides housing assistance and interest subsidy for EWS/LIG/MIG categories. Verify income slab at pmaymis.gov.in.",
        reason_fail="PMAY-U is for families without a pucca house in urban areas. Income limits apply (up to Rs 18 lakh/year).",
    ),
    _Rule(
        r"pmay[\s-]?g|pm\s*awas.*gramin|rural\s*housing",
        needs_bpl=True,
        reason_ok="PMAY-G provides Rs 1.2–1.3 lakh for rural housing to SECC 2011 listed households. Your profile aligns — check at Gram Panchayat.",
        reason_fail="PMAY-G targets BPL/SECC 2011 listed rural households without a pucca house.",
    ),
    _Rule(
        r"pmay.*clss|credit\s*linked\s*subsidy|clss",
        reason_ok="CLSS under PMAY gives interest subsidy on home loans for EWS/LIG/MIG — check income slab and apply at any bank.",
        reason_fail="CLSS requires income eligibility (up to Rs 18 lakh/year) and no existing pucca house.",
    ),

    # ── Energy ────────────────────────────────────────────────────────────────
    _Rule(
        r"ujjwala|lpg\s*connection|free\s*gas",
        needs_bpl=True,
        reason_ok="Ujjwala Yojana gives a free LPG connection to BPL women without an existing connection. Apply at the nearest LPG distributor.",
        reason_fail="Ujjwala targets BPL/priority households without an LPG connection. BPL status required.",
    ),
    _Rule(
        r"pm\s*surya\s*ghar|rooftop\s*solar|free\s*bijli|muft\s*bijli",
        reason_ok="PM Surya Ghar gives subsidy for rooftop solar and up to 300 free units/month. Apply at pmsuryaghar.gov.in if you own your home.",
        reason_fail="PM Surya Ghar requires a residential household with ownership and a valid electricity connection.",
    ),
    _Rule(
        r"saubhagya|free\s*electricity\s*connection|bijli\s*connection",
        needs_bpl=True,
        reason_ok="Saubhagya provides free electricity connection to BPL households. Contact your local DISCOM for doorstep enrollment.",
        reason_fail="Saubhagya gives free connections to un-electrified BPL households; APL households pay Rs 500 in installments.",
    ),
    _Rule(
        r"ddugjy|deendayal\s*gram\s*jyoti",
        needs_bpl=True,
        reason_ok="DDUGJY provides free electricity connections to rural BPL households. Register at Gram Panchayat or state electricity board.",
        reason_fail="DDUGJY free connections are for BPL rural households.",
    ),

    # ── Employment & Livelihoods ──────────────────────────────────────────────
    _Rule(
        r"mgnrega|mahatma\s*gandhi.*rural\s*employment|nrega",
        universal=True,
        reason_ok="MGNREGA guarantees 100 days of work/year to any adult rural household. Get a Job Card at your Gram Panchayat — free to apply.",
        reason_fail="MGNREGA is for adult members of rural households who volunteer for unskilled manual work.",
    ),
    _Rule(
        r"pmkvy|pradhan\s*mantri\s*kaushal|skill\s*india",
        reason_ok="PMKVY offers free skill training and certification for youth aged 15–45. Register at pmkvyofficial.org or a nearby training centre.",
        reason_fail="PMKVY is for Indian nationals aged 15–45 years with valid Aadhaar.",
    ),
    _Rule(
        r"naps\b|national\s*apprenticeship\s*promotion",
        needs_student=True,
        reason_ok="NAPS provides paid apprenticeships (Rs 1,500/month reimbursement to employer). Search openings at apprenticeshipindia.gov.in.",
        reason_fail="NAPS is for youth who have passed at least Class 5, aged 14–21.",
    ),
    _Rule(
        r"nats\b|national\s*apprenticeship\s*training",
        needs_student=True,
        reason_ok="NATS provides 1-year practical training for engineering diploma/degree holders with Rs 4,984–9,000/month stipend.",
        reason_fail="NATS is for diploma and engineering graduates under 35 years.",
    ),
    _Rule(
        r"pm\s*internship\s*scheme\s*2024|pm\s*internship",
        reason_ok="PM Internship gives Rs 5,000/month for 12 months in top 500 companies. Apply at pminternship.mca.gov.in if aged 21–24.",
        reason_fail="PM Internship is for youth aged 21–24, not in full-time employment/study, family income below Rs 8 lakh.",
    ),
    _Rule(
        r"nrlm|deendayal\s*antyodaya|self[\s-]?help\s*group|shg",
        needs_woman=True,
        needs_bpl=True,
        reason_ok="DAY-NRLM forms SHGs of rural BPL women and provides Rs 10,000 revolving fund + bank loans at 7%. Your profile fits.",
        reason_fail="DAY-NRLM targets rural BPL women aged 18–60 for SHG formation.",
    ),
    _Rule(
        r"ncs\s*portal|national\s*career\s*service",
        universal=True,
        reason_ok="NCS Portal is free for all job seekers. Register at ncs.gov.in to access 10 lakh+ job listings.",
        reason_fail="NCS Portal is open to all Indian citizens seeking employment.",
    ),
    _Rule(
        r"pm[\s-]?gkra|garib\s*kalyan\s*rozgar",
        needs_worker=True,
        reason_ok="PM-GKRA provides livelihood opportunities for migrant workers in 116 focus districts. Register at your Block Development Office.",
        reason_fail="PM-GKRA targets migrant workers returning to 6 states (Bihar, UP, MP, Rajasthan, Jharkhand, Odisha).",
    ),

    # ── Entrepreneurship ──────────────────────────────────────────────────────
    _Rule(
        r"stand[\s-]?up\s+india",
        needs_woman=True,
        needs_business_intent=True,
        reason_ok="Stand-Up India targets women / SC / ST entrepreneurs for loans of Rs 10 lakh – Rs 1 crore. Your profile aligns.",
        reason_fail="Stand-Up India is for SC/ST and women entrepreneurs setting up a new enterprise. Both conditions required.",
    ),
    _Rule(
        r"mudra|pm\s*mudra|pmmy",
        needs_business_intent=True,
        reason_ok="MUDRA supports micro/small enterprises with collateral-free loans (Rs 50K to Rs 20 lakh). Your business profile fits.",
        reason_fail="MUDRA is for non-farm income-generating micro-enterprises. Mention business/self-employment for eligibility.",
    ),
    _Rule(
        r"vishwakarma|pm\s*vishwakarma",
        needs_business_intent=True,
        reason_ok="PM Vishwakarma supports 18 traditional trades with toolkit (Rs 15K) + loans at 5%. Check if your craft/trade is listed.",
        reason_fail="PM Vishwakarma covers 18 listed traditional trades only (blacksmith, carpenter, potter, tailor, etc.).",
    ),
    _Rule(
        r"svanidhi|svAnidhi|street\s*vendor",
        needs_business_intent=True,
        reason_ok="PM SVANidhi provides collateral-free working capital loans (Rs 10K–50K) to street vendors. Apply at pmsvanidhi.mohua.gov.in.",
        reason_fail="PM SVANidhi is for street vendors with a Certificate of Vending or Letter of Recommendation.",
    ),
    _Rule(
        r"startup\s*india|dpiit",
        needs_business_intent=True,
        reason_ok="Startup India gives tax exemptions and patent rebates to DPIIT-recognised startups. Register at startupindia.gov.in.",
        reason_fail="Startup India is for companies/LLPs incorporated under 10 years with annual turnover under Rs 100 crore.",
    ),
    _Rule(
        r"pmfme|micro\s*food\s*process",
        needs_business_intent=True,
        reason_ok="PMFME offers 35% credit-linked subsidy (up to Rs 10 lakh) for micro food processing units. Apply at pmfme.mofpi.gov.in.",
        reason_fail="PMFME is for existing micro food-processing enterprises.",
    ),

    # ── Financial Inclusion ───────────────────────────────────────────────────
    _Rule(
        r"jan\s*dhan|pmjdy|zero\s*balance\s*account",
        universal=True,
        reason_ok="Jan Dhan zero-balance accounts are open to any Indian citizen above 10 years. Visit any bank branch with Aadhaar.",
        reason_fail="PMJDY is for Indian citizens above 10 years without a bank account.",
    ),
    _Rule(
        r"pmsby|suraksha\s*bima\s*yojana|accidental\s*insurance",
        universal=True,
        reason_ok="PMSBY costs just Rs 20/year and covers accidental death (Rs 2 lakh). Enrol at your bank or jansuraksha.gov.in.",
        reason_fail="PMSBY is for Indian residents aged 18–70 with a savings bank account.",
    ),
    _Rule(
        r"pmjjby|jeevan\s*jyoti\s*bima|life\s*insurance\s*436",
        universal=True,
        reason_ok="PMJJBY offers Rs 2 lakh life cover for just Rs 436/year. Enrol at your bank without a medical exam.",
        reason_fail="PMJJBY is for Indian residents aged 18–50 with a savings bank account.",
    ),

    # ── Pension & Social Security ─────────────────────────────────────────────
    _Rule(
        r"apy|atal\s*pension",
        universal=True,
        reason_ok="APY gives guaranteed Rs 1,000–5,000 pension/month after 60. Open at any bank for residents aged 18–40 who are not taxpayers.",
        reason_fail="APY is for Indian citizens aged 18–40 with a savings account, not covered by other pension schemes.",
    ),
    _Rule(
        r"pm[\s-]?sym|shram\s*yogi\s*maan[\s-]?dhan|unorganised\s*pension",
        needs_worker=True,
        reason_ok="PM-SYM gives Rs 3,000/month pension for unorganised workers. Enrol at CSC if aged 18–40 and earning below Rs 15,000/month.",
        reason_fail="PM-SYM is for unorganised workers aged 18–40 earning below Rs 15,000/month, not covered under EPFO/ESIC.",
    ),
    _Rule(
        r"nsap|national\s*social\s*assistance|old\s*age\s*pension|widow\s*pension",
        needs_bpl=True,
        reason_ok="NSAP provides monthly pension (Rs 200–500) to BPL elderly, widows, and disabled persons. Apply at Gram Panchayat.",
        reason_fail="NSAP is for BPL elderly (60+), widows (40+), and disabled persons (18+).",
    ),
    _Rule(
        r"vaya\s*vandana|pmvvy|senior\s*pension",
        needs_elderly=True,
        reason_ok="PMVVY gives 7.4% assured returns to senior citizens (60+) investing up to Rs 15 lakh via LIC.",
        reason_fail="PMVVY is exclusively for senior citizens aged 60 and above.",
    ),
    _Rule(
        r"nps\b|national\s*pension\s*system",
        universal=True,
        reason_ok="NPS is open to any Indian citizen aged 18–70. Open at any bank/post office with tax benefit of Rs 2 lakh/year.",
        reason_fail="NPS is for Indian citizens aged 18–70 seeking retirement savings.",
    ),
    _Rule(
        r"e[\s-]?shram",
        needs_worker=True,
        reason_ok="e-Shram provides a UAN card and Rs 2 lakh accident insurance to unorganised workers. Register free at eshram.gov.in.",
        reason_fail="e-Shram is for unorganised workers aged 16–59 not covered by EPFO/ESIC.",
    ),

    # ── Food Security ─────────────────────────────────────────────────────────
    _Rule(
        r"pm[\s-]?gkay|garib\s*kalyan\s*anna|free\s*food\s*grain",
        needs_bpl=True,
        reason_ok="PM-GKAY gives 5 kg free grains/month per person to NFSA ration card holders. Collect from your Fair Price Shop.",
        reason_fail="PM-GKAY is for Priority Household (PHH) or Antyodaya Anna Yojana (AAY) ration card holders.",
    ),
    _Rule(
        r"onorc|one\s*nation\s*one\s*ration",
        needs_bpl=True,
        reason_ok="ONORC lets you use your ration card at any FPS in India. Useful for migrants — no new card needed.",
        reason_fail="ONORC is for existing NFSA ration card holders (PHH/AAY).",
    ),
    _Rule(
        r"nfsa\s*ration|ration\s*card|antyodaya\s*anna",
        needs_bpl=True,
        reason_ok="NFSA ration cards give subsidised (now free) grains to BPL households. Apply at the Food & Civil Supplies office.",
        reason_fail="NFSA ration cards are for BPL households as identified by state governments.",
    ),
    _Rule(
        r"pm\s*poshan|mid[\s-]?day\s*meal",
        needs_student=True,
        reason_ok="PM Poshan provides free nutritious meals to all children in government school Classes 1–8. Enrol child in government school.",
        reason_fail="PM Poshan serves children in Classes 1–8 enrolled in government or government-aided schools.",
    ),

    # ── Education ─────────────────────────────────────────────────────────────
    _Rule(
        r"nsp\s*scholarship|national\s*scholarship\s*portal",
        needs_student=True,
        reason_ok="NSP scholarships are available for SC/ST/OBC/Minority students at all levels. Apply at scholarships.gov.in before October.",
        reason_fail="NSP scholarships are for SC/ST/OBC/Minority/Differently-abled students with minimum 50% marks.",
    ),
    _Rule(
        r"sc\s*post[\s-]?matric|post\s*matric.*sc",
        needs_student=True,
        reason_ok="SC Post-Matric Scholarship covers fees + maintenance (Rs 380–1,200/month) for SC students in Class 11+. Apply at scholarships.gov.in.",
        reason_fail="SC Post-Matric Scholarship requires SC category + parental income below Rs 2.5 lakh/year.",
    ),
    _Rule(
        r"pre[\s-]?matric.*sc.?st|sc.?st.*pre[\s-]?matric",
        needs_student=True,
        reason_ok="Pre-Matric SC/ST Scholarship supports Class 9–10 students. Apply at scholarships.gov.in before October.",
        reason_fail="Pre-Matric SC/ST Scholarship is for SC/ST students in Classes 9–10 with parental income below Rs 2 lakh.",
    ),
    _Rule(
        r"national\s*overseas\s*scholarship",
        needs_student=True,
        reason_ok="National Overseas Scholarship covers full PhD/post-doc abroad for SC/ST students below 35 with 55%+ marks. Apply at nosmsje.gov.in.",
        reason_fail="National Overseas Scholarship is for SC/ST students below 35 years with Master's degree and 55%+ marks.",
    ),
    _Rule(
        r"pm\s*evidya|diksha|swayam",
        needs_student=True,
        reason_ok="PM eVIDYA provides free digital learning via DIKSHA, SWAYAM PRABHA TV, and online courses for school/college students.",
        reason_fail="PM eVIDYA is for school and college students seeking digital learning resources.",
    ),
    _Rule(
        r"pmss\s*capf|pm\s*scholarship.*capf|capf\s*scholarship",
        needs_student=True,
        reason_ok="PMSS CAPF gives Rs 2,500–3,000/month to wards of CAPF/RPF personnel who died/disabled in duty. Apply at ksb.gov.in.",
        reason_fail="PMSS CAPF is for wards/widows of CAPF and RPF personnel; 60%+ marks in Class 12 required.",
    ),

    # ── Sanitation & Water ────────────────────────────────────────────────────
    _Rule(
        r"swachh\s*bharat|toilet\s*(construction|incentive)|ihhl",
        needs_bpl=True,
        reason_ok="SBM-G gives Rs 12,000 to BPL rural households for toilet construction. Apply at Gram Panchayat.",
        reason_fail="SBM-G incentive is for BPL/SC/ST/small-marginal farmer rural households without a household toilet.",
    ),
    _Rule(
        r"jal\s*jeevan|har\s*ghar\s*jal|tap\s*water\s*connection",
        universal=True,
        reason_ok="Jal Jeevan Mission provides tap water connections to all rural households. Contact Gram Panchayat if your house lacks a connection.",
        reason_fail="Jal Jeevan Mission is for rural households without a functional tap water connection.",
    ),

    # ── Digital Services ──────────────────────────────────────────────────────
    _Rule(
        r"csc|common\s*service\s*cent(re|er)|digital\s*india",
        universal=True,
        reason_ok="CSCs are open to all citizens for 300+ government services. Find your nearest CSC at locator.csc.gov.in.",
        reason_fail="CSCs serve all citizens; no eligibility restriction.",
    ),

    # ── Investment ────────────────────────────────────────────────────────────
    _Rule(
        r"sovereign\s*gold\s*bond|sgb\b",
        universal=True,
        reason_ok="Sovereign Gold Bond is open to Indian residents, HUFs, trusts, and universities. Buy during subscription windows at banks/post offices.",
        reason_fail="SGB is for Indian residents; max 4 kg/year per individual.",
    ),

    # ── Disability ────────────────────────────────────────────────────────────
    _Rule(
        r"divyangjan|adip|disability\s*assist|nhfdc",
        reason_ok="Divyangjan schemes provide assistive devices (ADIP up to Rs 10K) and self-employment loans (5% interest). Disability certificate (40%+) required.",
        reason_fail="Divyangjan schemes require a disability certificate showing 40%+ disability from CMO/SADGM.",
    ),

    # ── Urban Development ─────────────────────────────────────────────────────
    _Rule(
        r"amrut|smart\s*cit(y|ies)|urban\s*transform",
        universal=True,
        reason_ok="AMRUT and Smart Cities improve urban infrastructure. Citizens can track projects and raise grievances at amrut.gov.in or smartcities.gov.in.",
        reason_fail="AMRUT and Smart Cities are implemented at city/ULB level; no individual application required.",
    ),
    _Rule(
        r"swachh\s*survekshan",
        universal=True,
        reason_ok="Swachh Survekshan lets citizens rate their city's cleanliness. Submit feedback on the Swachh Bharat app.",
        reason_fail="Swachh Survekshan is open to all urban citizens for feedback.",
    ),

    # ── State — Karnataka ─────────────────────────────────────────────────────
    _Rule(
        r"gruha\s*lakshmi",
        needs_woman=True,
        reason_ok="Gruha Lakshmi gives Rs 2,000/month to woman head of BPL/APL household in Karnataka. Apply at Seva Sindhu portal.",
        reason_fail="Gruha Lakshmi is for the woman head of an eligible household with a Karnataka ration card; not a government employee/taxpayer.",
    ),
    _Rule(
        r"shakti\s*(scheme|smart\s*card|bus)",
        needs_woman=True,
        reason_ok="Shakti Scheme gives free bus travel to all women in Karnataka. Get your Shakti Smart Card at the nearest KSRTC/BMTC depot with Aadhaar.",
        reason_fail="Shakti is for all women and transgender persons residing in Karnataka.",
    ),
    _Rule(
        r"anna\s*bhagya",
        needs_bpl=True,
        reason_ok="Anna Bhagya gives 10 kg free rice/month to BPL and AAY ration card holders in Karnataka.",
        reason_fail="Anna Bhagya is for BPL (yellow/priority) and Antyodaya ration card holders in Karnataka.",
    ),
    _Rule(
        r"yuva\s*nidhi",
        needs_student=True,
        reason_ok="Yuva Nidhi gives Rs 3,000/month (graduates) or Rs 1,500/month (diploma) to unemployed youth in Karnataka for up to 2 years.",
        reason_fail="Yuva Nidhi is for Karnataka-domicile unemployed graduates/diploma holders within 2 years of completion.",
    ),

    # ── State — Andhra Pradesh ────────────────────────────────────────────────
    _Rule(
        r"rythu\s*bharosa",
        needs_farmer=True,
        reason_ok="Rythu Bharosa gives Rs 13,500/year (state Rs 7,500 + PM-KISAN Rs 6,000) to AP farmers. Verify with village revenue officer.",
        reason_fail="Rythu Bharosa is for farmers with land records in Andhra Pradesh.",
    ),
    _Rule(
        r"ysr\s*pension\s*kanuka",
        needs_elderly=True,
        reason_ok="YSR Pension Kanuka gives Rs 2,750–3,000/month to elderly, widows, and disabled in AP. Apply at Ward Volunteer.",
        reason_fail="YSR Pension Kanuka targets elderly (65+), widows, disabled, and other specified categories in Andhra Pradesh.",
    ),

    # ── State — Tamil Nadu ────────────────────────────────────────────────────
    _Rule(
        r"pudhumai\s*penn",
        needs_woman=True,
        needs_student=True,
        reason_ok="Pudhumai Penn gives Rs 1,000/month to girl students in Tamil Nadu government schools (Class 6+). Apply through school/college.",
        reason_fail="Pudhumai Penn is for girl students in Tamil Nadu government schools transitioning to government colleges.",
    ),
    _Rule(
        r"magalir\s*urimai|kalaignar\s*magalir",
        needs_woman=True,
        reason_ok="Magalir Urimai gives Rs 1,000/month to woman heads of eligible households in Tamil Nadu. Apply at Ward/Village Secretariat.",
        reason_fail="Magalir Urimai targets women who are heads of family in Tamil Nadu with income below Rs 2.5 lakh/year.",
    ),

    # ── State — Madhya Pradesh ────────────────────────────────────────────────
    _Rule(
        r"ladli\s*behna",
        needs_woman=True,
        reason_ok="Ladli Behna gives Rs 1,250/month to eligible women in Madhya Pradesh. Apply at Gram Panchayat camp with Aadhaar and Samagra ID.",
        reason_fail="Ladli Behna is for MP women aged 21–60, income below Rs 2.5 lakh/year, not a government employee or taxpayer.",
    ),
    _Rule(
        r"cm\s*kisan\s*kalyan|mukhyamantri\s*kisan\s*kalyan",
        needs_farmer=True,
        reason_ok="CM Kisan Kalyan (MP) gives additional Rs 4,000/year to PM-KISAN registered farmers in Madhya Pradesh. No separate application.",
        reason_fail="CM Kisan Kalyan is for PM-KISAN registered farmers in Madhya Pradesh.",
    ),
    _Rule(
        r"seekho\s*kamao|mukhyamantri.*seekho|mmsky",
        reason_ok="Seekho Kamao (MP) pays Rs 8,000–10,000/month stipend while you train at registered industries. Register at mmsky.mp.gov.in if aged 18–29.",
        reason_fail="Seekho Kamao is for MP domicile youth aged 18–29; stipend varies by qualification.",
    ),

    # ── State — Assam ─────────────────────────────────────────────────────────
    _Rule(
        r"orunodoi",
        needs_woman=True,
        reason_ok="Orunodoi gives Rs 1,250/month to economically weaker families in Assam, paid to the woman member. Apply at orunodoi.assam.gov.in.",
        reason_fail="Orunodoi is for families in Assam with income below Rs 2 lakh/year, no government employee, and no 4-wheeler.",
    ),

    # ── State — West Bengal ───────────────────────────────────────────────────
    _Rule(
        r"lakshmir\s*bhandar|laxmir\s*bhandar",
        needs_woman=True,
        reason_ok="Lakshmir Bhandar gives Rs 500–1,000/month to woman heads of household in West Bengal. Apply at Duare Sarkar camp.",
        reason_fail="Lakshmir Bhandar is for women aged 25–60 who are heads of family in West Bengal with a ration card.",
    ),
    _Rule(
        r"swasthya\s*sathi",
        universal=True,
        reason_ok="Swasthya Sathi gives Rs 5 lakh health cover to all WB families. Enrol at nearest camp or swasthyasathi.gov.in.",
        reason_fail="Swasthya Sathi is for all families in West Bengal regardless of income.",
    ),

    # ── State — Delhi ─────────────────────────────────────────────────────────
    _Rule(
        r"mahila\s*samman.*delhi|delhi.*mahila\s*samman",
        needs_woman=True,
        reason_ok="Delhi Mahila Samman gives Rs 1,000/month to eligible Delhi women. Check delhigovt.nic.in for application status.",
        reason_fail="Delhi Mahila Samman is for women above 18 who are permanent Delhi residents for 5+ years, not government employees.",
    ),

    # ── State — Maharashtra ───────────────────────────────────────────────────
    _Rule(
        r"mahadbt|maharashtra.*scholarship",
        needs_student=True,
        reason_ok="Mahadbt is Maharashtra's scholarship portal for 40+ schemes. Apply at mahadbt.maharashtra.gov.in before deadline.",
        reason_fail="Mahadbt scholarships are for Maharashtra students across SC/ST/OBC/Minority/SBC categories.",
    ),
    _Rule(
        r"ladki\s*bahin|majhi\s*ladki\s*bahin",
        needs_woman=True,
        reason_ok="Ladki Bahin gives Rs 1,500/month to eligible women in Maharashtra. Apply at nari.maharashtra.gov.in.",
        reason_fail="Ladki Bahin is for Maharashtra women aged 21–65 with family income below Rs 2.5 lakh/year.",
    ),

    # ── State — Rajasthan ─────────────────────────────────────────────────────
    _Rule(
        r"chiranjeevi\s*bima|chiranjeevi\s*swasthya",
        universal=True,
        reason_ok="Chiranjeevi gives Rs 25 lakh health cover in Rajasthan. BPL families are free; others pay Rs 850/year premium.",
        reason_fail="Chiranjeevi is for all Rajasthan families; premium waived for BPL and NFSA beneficiaries.",
    ),
    _Rule(
        r"indira\s*shahri\s*rozgar|urban\s*rozgar\s*rajasthan",
        reason_ok="Indira Shahri Rozgar gives 125 days of urban employment/year to Rajasthan residents. Register at your Urban Local Body.",
        reason_fail="Indira Shahri Rozgar is for adult members of urban households in Rajasthan.",
    ),

    # ── State — Bihar ─────────────────────────────────────────────────────────
    _Rule(
        r"yuva\s*udyami.*bihar|cm.*udyami.*bihar",
        needs_business_intent=True,
        reason_ok="CM Yuva Udyami Bihar gives interest-free Rs 10 lakh loan to SC/ST youth in Bihar for new enterprises. Apply at udyami.bihar.gov.in.",
        reason_fail="CM Yuva Udyami Bihar is for SC/ST Bihar domicile youth aged 18–50 with at least Class 10 qualification.",
    ),
)


# ── needs_business_intent alias (dataclass field named differently above) ──

def _needs_business(rule: _Rule) -> bool:
    return rule.needs_business_intent


# ── main public function ──────────────────────────────────────────────────────

def hints_for_schemes(
    profile: dict | None,
    results: list[SearchResult],
    *,
    query: str = "",
) -> list[dict]:
    """Return small verdict hints for top retrieved schemes (best-effort, not legal advice)."""
    p = profile or {}
    blob = _text_profile(p)
    combined = f"{blob} {(query or '').lower()}".strip()

    out: list[dict] = []
    for r in results[:5]:
        name = (r.scheme_name or "").strip()
        if not name:
            continue
        lower = name.lower()

        matched: _Rule | None = None
        for rule in _RULES:
            if re.search(rule.pattern, lower, re.I):
                matched = rule
                break

        if not matched:
            # Generic fallback — always give something useful
            out.append({
                "scheme": name,
                "verdict": "unknown",
                "reason": "Verify your eligibility at the official portal or nearest CSC — no quick criteria available.",
            })
            continue

        if matched.universal:
            out.append({"scheme": name, "verdict": "likely_eligible", "reason": matched.reason_ok})
            continue

        ok = True
        if matched.needs_woman and not _has_woman(combined):
            ok = False
        if matched.needs_business_intent and not _has_business(combined):
            ok = False
        if matched.needs_farmer and not _has_farmer(combined):
            ok = False
        if matched.needs_student and not _has_student(combined):
            ok = False
        if matched.needs_elderly and not _has_elderly(combined):
            ok = False
        if matched.needs_bpl and not _has_bpl(combined):
            ok = False
        if matched.needs_worker and not _has_worker(combined):
            ok = False

        verdict = "likely_eligible" if ok else "likely_ineligible"
        reason = matched.reason_ok if ok else matched.reason_fail
        out.append({"scheme": name, "verdict": verdict, "reason": reason})

    return out
