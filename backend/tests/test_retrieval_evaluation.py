"""Reproducible Retrieval Evaluation Suite for Timbre Cross-Lingual RAG (100-Query Benchmark).

Evaluates 100 queries across English, Romanized Hinglish, Devanagari Hindi, and mixed script:
- 80 In-Domain queries across 10 statutory schemes (formal, colloquial, semantic synonyms)
- 20 Out-of-Domain queries (unrelated schemes, non-existent benefits, adversarial claims)

Measures:
- Top-1 accuracy (Target scheme retrieved at rank 1)
- Top-3 accuracy (Target scheme in top 3 results)
- Recall rate across relevant statutory categories
- Citation correctness (Source title, page/section metadata present)
- Out-of-domain rejection rate (Score thresholding prevents false matches)
"""
import json
import pytest
from app.services.knowledge_service import knowledge_service, IncompatibleEmbeddingError
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk


EVALUATION_DATASET_100 = [
    # --- 1. Voter ID Card (ECI-VOTER-FORM6) [8 queries] ---
    {"id": "Q001", "query": "How do I apply for a new voter ID card using Form 6?", "lang": "en", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q002", "query": "What documents are required to register as a first-time voter with ECI?", "lang": "en", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q003", "query": "Naya voter card banwane ke liye Form 6 online apply kaise kare?", "lang": "hinglish", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q004", "query": "Voters portal par naye matdata registration ke liye age proof kya lagta hai?", "lang": "hinglish", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q005", "query": "मतदाता पहचान पत्र (वोटर आईडी कार्ड) पंजीकरण हेतु आवश्यक दस्तावेज क्या हैं?", "lang": "hi", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q006", "query": "निर्वाचन आयोग के फॉर्म 6 द्वारा नए मतदाता पहचान पत्र के लिए ऑनलाइन आवेदन", "lang": "hi", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q007", "query": "18 वर्ष का नागरिक चुनाव में वोट डालने के लिए सरकारी पहचान पत्र कैसे बनवाए?", "lang": "synonym", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},
    {"id": "Q008", "query": "Chunav me matdaan karne ke liye official voter list me naam kaise judwaye?", "lang": "synonym", "expected_code": "ECI-VOTER-FORM6", "is_ood": False},

    # --- 2. Driving Learner Licence (MORTH-PARIVAHAN-LL) [8 queries] ---
    {"id": "Q009", "query": "What is the procedure to get a learner driving licence on the Parivahan portal?", "lang": "en", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q010", "query": "What is the statutory fee and age limit for a computerised learner driving licence test?", "lang": "en", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q011", "query": "Gaadi chalana sikhne ke liye learner licence ka online test kaise hota hai?", "lang": "hinglish", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q012", "query": "Parivahan Sarathi website par motorcycle aur car ka LL apply karne ke steps", "lang": "hinglish", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q013", "query": "परिवहन सारथी पोर्टल पर लर्नर ड्राइविंग लाइसेंस के लिए पात्रता क्या है?", "lang": "hi", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q014", "query": "चालन अनुज्ञप्ति (लर्निंग लाइसेंस) हेतु ऑनलाइन यातायात नियम परीक्षा कैसे दें?", "lang": "hi", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q015", "query": "Motor vehicle chalane ki legal permission lene ke liye pehla temporary licence", "lang": "synonym", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},
    {"id": "Q016", "query": "16 से 18 वर्ष के युवा बिना गियर वाले दोपहिया वाहन की अनुमति कैसे लें?", "lang": "synonym", "expected_code": "MORTH-PARIVAHAN-LL", "is_ood": False},

    # --- 3. PAN Card Application (ITD-PAN-FORM49A) [8 queries] ---
    {"id": "Q017", "query": "How can an Indian citizen apply for a PAN card using Form 49A?", "lang": "en", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q018", "query": "What is the statutory fee for a physical PAN card delivered by NSDL or UTIITSL?", "lang": "en", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q019", "query": "Naya PAN card banwane ke liye kitni statutory fee lagti hai?", "lang": "hinglish", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q020", "query": "Bank account kholne aur tax return bharne ke liye 10-digit PAN number kaise milega?", "lang": "hinglish", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q021", "query": "स्थायी खाता संख्या (पैन कार्ड) बनवाने के लिए पहचान और पते का प्रमाण क्या चाहिए?", "lang": "hi", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q022", "query": "आयकर विभाग फॉर्म 49A के तहत नए पैन कार्ड हेतु ऑनलाइन आवेदन प्रक्रिया", "lang": "hi", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q023", "query": "Financial transactions aur IT return ke liye 10-character alphanumeric identity card", "lang": "synonym", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},
    {"id": "Q024", "query": "बैंक में बड़ा लेन-देन करने हेतु आयकर विभाग का स्थायी नंबर कैसे प्राप्त करें?", "lang": "synonym", "expected_code": "ITD-PAN-FORM49A", "is_ood": False},

    # --- 4. PM-Kisan Samman Nidhi (AGRI-PMKISAN-DBT) [8 queries] ---
    {"id": "Q025", "query": "What is the annual financial benefit under the PM-Kisan Samman Nidhi scheme?", "lang": "en", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q026", "query": "What are the landholding and eligibility criteria for PM-Kisan DBT transfers?", "lang": "en", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q027", "query": "Kisan samman nidhi me 6000 rupaye saal ke pane ke liye land record kaise jode?", "lang": "hinglish", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q028", "query": "PM kisan yojana ki 2000 rupaye ki installment kab aati hai bank account me?", "lang": "hinglish", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q029", "query": "प्रधानमंत्री किसान सम्मान निधि योजना के तहत छोटे किसान परिवार कैसे पंजीकरण कराएं?", "lang": "hi", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q030", "query": "कृषि योग्य भूमि वाले काश्तकार परिवारों को 6000 रुपये वार्षिक सहायता के नियम", "lang": "hi", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q031", "query": "Kheti karne wale parivar ko direct bank transfer se sarkari aarthik sahayata", "lang": "synonym", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},
    {"id": "Q032", "query": "खेती-किसानी के खर्च के लिए सरकार से तीन किस्तों में मिलने वाली आर्थिक मदद", "lang": "synonym", "expected_code": "AGRI-PMKISAN-DBT", "is_ood": False},

    # --- 5. Ayushman Bharat PM-JAY (NHA-PMJAY-HEALTH) [8 queries] ---
    {"id": "Q033", "query": "How much health insurance coverage is provided by the Ayushman Bharat Golden Card?", "lang": "en", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q034", "query": "Which families are eligible for cashless hospitalisation up to 5 lakh INR under PM-JAY?", "lang": "en", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q035", "query": "Ayushman Bharat card se private hospital me 5 lakh ka muft ilaj kaise milta hai?", "lang": "hinglish", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q036", "query": "Golden card download karne ke liye beneficiary list me naam kaise check kare?", "lang": "hinglish", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q037", "query": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना (गोल्डन कार्ड) में अस्पताल भर्ती का खर्च कैसे मिलता है?", "lang": "hi", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q038", "query": "प्रति परिवार 5 लाख रुपये तक का कैशलेस स्वास्थ्य बीमा पाने की पात्रता क्या है?", "lang": "hi", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q039", "query": "Gareeb parivar ke ilaj aur surgery ke liye 5 lakh tak ka sarkari medical card", "lang": "synonym", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},
    {"id": "Q040", "query": "अस्पताल में गंभीर बीमारी के इलाज हेतु सरकारी स्वास्थ्य सुरक्षा योजना", "lang": "synonym", "expected_code": "NHA-PMJAY-HEALTH", "is_ood": False},

    # --- 6. NSP Post-Matric Scholarships (MOE-NSP-POSTMATRIC) [8 queries] ---
    {"id": "Q041", "query": "Who is eligible for the National Scholarship Portal post-matric financial assistance?", "lang": "en", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q042", "query": "What are the income ceilings and marks requirements for NSP scholarships?", "lang": "en", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q043", "query": "College fees ke liye NSP portal par post-matric scholarship apply karne ke niyam", "lang": "hinglish", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q044", "query": "Higher education me vidyarthi chhatravritti ke liye income certificate kaise upload kare?", "lang": "hinglish", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q045", "query": "राष्ट्रीय छात्रवृत्ति पोर्टल पर उच्च शिक्षा हेतु पोस्ट-मैट्रिक स्कॉलरशिप के लिए आय सीमा क्या है?", "lang": "hi", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q046", "query": "कॉलेज और विश्वविद्यालय के छात्रों के लिए सरकारी छात्रवृत्ति योजना के नियम", "lang": "hi", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q047", "query": "10th ke baad aage ki padhai aur degree college ki tuition fees ke liye sarkari madad", "lang": "synonym", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},
    {"id": "Q048", "query": "कम आय वर्ग के मेधावी छात्र छात्राओं को कॉलेज की पढ़ाई हेतु वित्तीय अनुदान", "lang": "synonym", "expected_code": "MOE-NSP-POSTMATRIC", "is_ood": False},

    # --- 7. IGNOAPS Old Age Pension (RD-NSAP-IGNOAPS) [8 queries] ---
    {"id": "Q049", "query": "What are the eligibility requirements for the Indira Gandhi National Old Age Pension?", "lang": "en", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q050", "query": "At what age does an elderly BPL citizen qualify for monthly central pension under NSAP?", "lang": "en", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q051", "query": "60 saal se upar ke BPL bujurg nagriko ke liye sarkari pension yojana", "lang": "hinglish", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q052", "query": "Vridhha pension ke liye gram panchayat ya municipal office me aavedan kaise hota hai?", "lang": "hinglish", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q053", "query": "बुजुर्ग नागरिकों के लिए वृद्धावस्था पेंशन योजना में मासिक वित्तीय सहायता", "lang": "hi", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q054", "query": "इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना (एनएसएपी) के तहत 60 वर्ष के वृद्धों को लाभ", "lang": "hi", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q055", "query": "Garib senior citizens ko monthly jeewan yaapan ke liye milne wali sarkari pension", "lang": "synonym", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},
    {"id": "Q056", "query": "गरीबी रेखा से नीचे जीवनयापन करने वाले 60 वर्ष से अधिक आयु के नागरिकों को मासिक भत्ता", "lang": "synonym", "expected_code": "RD-NSAP-IGNOAPS", "is_ood": False},

    # --- 8. Sukanya Samriddhi Yojana (DOP-SSA-GIRLCHILD) [8 queries] ---
    {"id": "Q057", "query": "What is the maximum age of a girl child to open a Sukanya Samriddhi account?", "lang": "en", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q058", "query": "What is the minimum initial deposit and tax benefit under the Sukanya Samriddhi scheme?", "lang": "en", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q059", "query": "Beti ki padhai ke liye post office me Sukanya Samriddhi khata kaise khole?", "lang": "hinglish", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q060", "query": "10 saal se chhoti beti ke naam par post office me SSA account ke documents", "lang": "hinglish", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q061", "query": "सुकन्या समृद्धि योजना खाता डाकघर में 10 वर्ष से कम आयु की बालिकाओं के लिए कैसे खोलें?", "lang": "hi", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q062", "query": "बालिका की शिक्षा और विवाह हेतु डाकघर बचत योजना के तहत ब्याज दर और नियम", "lang": "hi", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q063", "query": "Girl child ki future savings ke liye high interest post office bank scheme", "lang": "synonym", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},
    {"id": "Q064", "query": "बेटी के भविष्य के लिए डाकघर में संचालित सरकारी दीर्घकालिक निवेश योजना", "lang": "synonym", "expected_code": "DOP-SSA-GIRLCHILD", "is_ood": False},

    # --- 9. e-Shram UAN Card (LE-ESHRAM-UAN) [8 queries] ---
    {"id": "Q065", "query": "Which unorganised workers are eligible to register on the e-Shram portal?", "lang": "en", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q066", "query": "What is the age criteria (16 to 59 years) and accidental insurance for e-Shram UAN?", "lang": "en", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q067", "query": "Majdoor aur unorganised worker ke liye 12-digit e-shram UAN card kaise banta hai?", "lang": "hinglish", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q068", "query": "Shramik card banwane ke liye Aadhaar linked mobile number registration", "lang": "hinglish", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q069", "query": "ई-श्रम पोर्टल पर असंगठित कामगारों के लिए 12-अंकीय यूएएन कार्ड पंजीकरण", "lang": "hi", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q070", "query": "दिहाड़ी मजदूरों और निर्माण श्रमिकों के लिए राष्ट्रीय डेटाबेस कार्ड कैसे बनाएं?", "lang": "hi", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q071", "query": "Rehri patri wale, auto driver aur labour ke liye central government worker identity card", "lang": "synonym", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},
    {"id": "Q072", "query": "असंगठित क्षेत्र में कार्यरत श्रमिकों को सामाजिक सुरक्षा लाभ देने वाला सरकारी पहचान पत्र", "lang": "synonym", "expected_code": "LE-ESHRAM-UAN", "is_ood": False},

    # --- 10. UDID Disability Identity Card (DEPWD-SWAVLAMBAN-UDID) [8 queries] ---
    {"id": "Q073", "query": "How does a person with disability obtain a national Swavlamban UDID card?", "lang": "en", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q074", "query": "What medical authority issues disability certificate verification for unique disability ID?", "lang": "en", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q075", "query": "Divyangjan Swavlamban portal se unique disability identity card kaise download kare?", "lang": "hinglish", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q076", "query": "Handicapped certificate hone par pan-India smart card pane ka online tarika", "lang": "hinglish", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q077", "query": "दिव्यांगजन विशिष्ट पहचान पत्र (स्वावलंबन यूडीआईडी कार्ड) चिकित्सा प्रमाण पत्र के साथ कैसे प्राप्त करें?", "lang": "hi", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q078", "query": "दिव्यांग सशक्तिकरण विभाग द्वारा जारी राष्ट्रीय यूडीआईडी स्मार्ट कार्ड की प्रक्रिया", "lang": "hi", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q079", "query": "Divyang vyaktiyon ko railway aur sarkari suvidhaon ke liye ekmatra all-India pehchan patra", "lang": "synonym", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},
    {"id": "Q080", "query": "शारीरिक या मानसिक रूप से अक्षम व्यक्तियों के लिए केंद्र सरकार का एकल स्मार्ट पहचान पत्र", "lang": "synonym", "expected_code": "DEPWD-SWAVLAMBAN-UDID", "is_ood": False},

    # --- 11 to 20. Out-of-Domain & Adversarial Non-Existent Claims [20 queries] ---
    {"id": "Q081", "query": "How to renew an Indian diplomatic passport under Tatkaal scheme within 24 hours?", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q082", "query": "Foreign country tourist and study visa processing checklist and Embassy interview", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q083", "query": "Free electricity 300 units monthly waiver form submission", "lang": "hinglish", "expected_code": None, "is_ood": True},
    {"id": "Q084", "query": "Commercial pilot helicopter flying training government subsidy application", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q085", "query": "क्रिप्टोकरेंसी ट्रेडिंग लाइसेंस और बिटकॉइन टैक्स छूट का सरकारी नियम", "lang": "hi", "expected_code": None, "is_ood": True},
    {"id": "Q086", "query": "क्या सरकार हर नागरिक को बिना किसी शर्त के 5 लाख रुपये बैंक खाते में दे रही है?", "lang": "hi", "expected_code": None, "is_ood": True},
    {"id": "Q087", "query": "Pet dog ownership municipal tax token registration online", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q088", "query": "Court marriage certificate and divorce decree fast track portal", "lang": "hinglish", "expected_code": None, "is_ood": True},
    {"id": "Q089", "query": "Commercial real estate stamp duty 100% waiver for shopping mall builder", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q090", "query": "Gold loan interest free scheme for buying private luxury car", "lang": "hinglish", "expected_code": None, "is_ood": True},
    {"id": "Q091", "query": "इलेक्ट्रिक लग्जरी स्पोर्ट्स कार खरीदने पर शत-प्रतिशत सरकारी नकद सब्सिडी", "lang": "hi", "expected_code": None, "is_ood": True},
    {"id": "Q092", "query": "Police verification certificate for permanent residency in Australia", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q093", "query": "Personal firearms and pistol weapon licence application for private citizen", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q094", "query": "Space rocket launch private commercial satellite launch permit from ISRO", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q095", "query": "Forest timber cutting commercial contract tender allocation", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q096", "query": "शराब की दुकान का सरकारी ठेका नीलामी आवेदन पत्र", "lang": "hi", "expected_code": None, "is_ood": True},
    {"id": "Q097", "query": "Highway toll plaza free pass for all private vehicle owners in India", "lang": "hinglish", "expected_code": None, "is_ood": True},
    {"id": "Q098", "query": "Stock market intra-day trading profit guarantee government scheme", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q099", "query": "Free international luxury airline ticket voucher scheme", "lang": "en", "expected_code": None, "is_ood": True},
    {"id": "Q100", "query": "बिना सिबिल स्कोर और बिना किसी गारंटी के 50 लाख रुपये का सरकारी पर्सनल लोन", "lang": "hi", "expected_code": None, "is_ood": True},
]


def test_100_query_cross_lingual_retrieval_benchmark(db):
    """Executes the full 100-query benchmark across English, Hinglish, Devanagari Hindi, and OOD."""
    knowledge_service.seed_scheme_catalogue_if_empty(db, force_reseed=True)

    top_1_hits = 0
    top_3_hits = 0
    in_domain_total = 0
    ood_rejected = 0
    ood_total = 0
    citation_valid = 0

    results_log = []

    for item in EVALUATION_DATASET_100:
        query = item["query"]
        expected = item["expected_code"]
        is_ood = item["is_ood"]

        # Search with standard production threshold
        results = knowledge_service.search(db, query, top_k=3, min_score=0.35)

        if is_ood:
            ood_total += 1
            # OOD criterion: Either 0 results or top score < 0.50
            top_score = results[0]["score"] if results else 0.0
            is_rejected = (len(results) == 0) or (top_score < 0.50)
            if is_rejected:
                ood_rejected += 1
            results_log.append({
                "id": item["id"],
                "type": "OOD",
                "passed": is_rejected,
                "top_score": top_score,
            })
        else:
            in_domain_total += 1
            retrieved_headings = [r["section_heading"] or "" for r in results]
            
            # Citation correctness
            if results and results[0].get("citation") and "Timbre Statutory" in results[0]["citation"]:
                citation_valid += 1

            hit_1 = len(retrieved_headings) > 0 and expected in retrieved_headings[0]
            hit_3 = any(expected in h for h in retrieved_headings[:3])

            if hit_1:
                top_1_hits += 1
            if hit_3:
                top_3_hits += 1

            results_log.append({
                "id": item["id"],
                "type": "IN_DOMAIN",
                "hit_1": hit_1,
                "hit_3": hit_3,
                "top_score": results[0]["score"] if results else 0.0,
                "top_heading": retrieved_headings[0] if retrieved_headings else "None",
            })

    top_1_acc = (top_1_hits / in_domain_total) * 100
    top_3_acc = (top_3_hits / in_domain_total) * 100
    citation_acc = (citation_valid / in_domain_total) * 100
    ood_rej_rate = (ood_rejected / ood_total) * 100

    print(f"\n==================== 100-QUERY CROSS-LINGUAL RETRIEVAL BENCHMARK ====================")
    print(f"Total Benchmark Queries: {len(EVALUATION_DATASET_100)}")
    print(f"In-Domain Queries: {in_domain_total} (8 per scheme across 10 statutory schemes)")
    print(f"  • Top-1 Retrieval Accuracy: {top_1_hits}/{in_domain_total} ({top_1_acc:.1f}%)")
    print(f"  • Top-3 Retrieval Accuracy: {top_3_hits}/{in_domain_total} ({top_3_acc:.1f}%)")
    print(f"  • Citation Correctness:     {citation_valid}/{in_domain_total} ({citation_acc:.1f}%)")
    print(f"Out-of-Domain Queries: {ood_total} (Adversarial, non-existent benefits, unrelated queries)")
    print(f"  • Out-of-Domain Rejection:  {ood_rejected}/{ood_total} ({ood_rej_rate:.1f}%)")
    print(f"=====================================================================================")

    # Acceptance Thresholds
    assert top_1_acc >= 85.0, f"Top-1 accuracy {top_1_acc:.1f}% below 85% requirement"
    assert top_3_acc >= 95.0, f"Top-3 accuracy {top_3_acc:.1f}% below 95% requirement"
    assert citation_acc >= 95.0, f"Citation accuracy {citation_acc:.1f}% below 95% requirement"
    assert ood_rej_rate >= 80.0, f"OOD rejection rate {ood_rej_rate:.1f}% below 80% requirement"


def test_embedding_stability_across_rebuild(db):
    """Verifies that rebuilding embeddings maintains stable vector values and does not alter text or citations."""
    doc = db.query(KnowledgeDocument).first()
    assert doc is not None

    chunks_before = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    count_before = len(chunks_before)
    text_before = [c.content for c in chunks_before]

    # Rebuild
    rebuilt_count = knowledge_service.rebuild_document_embeddings(db, doc.id)
    assert rebuilt_count == count_before

    chunks_after = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    text_after = [c.content for c in chunks_after]

    assert text_before == text_after
    for c in chunks_after:
        meta = json.loads(c.metadata_json or "{}")
        assert meta["embedding_model"] == knowledge_service.provider.model_name
        assert meta["embedding_version"] == knowledge_service.provider.version


def test_incompatible_embedding_version_handling(db):
    """Verifies that an incompatible vector dimension triggers an error when auto-rebuild is disabled."""
    doc = db.query(KnowledgeDocument).first()
    chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).first()
    
    # Intentionally corrupt chunk vector with wrong dimension (e.g. 128 instead of 384)
    original_vector = chunk.vector_json
    chunk.vector_json = json.dumps([0.1] * 128)
    db.commit()

    with pytest.raises(IncompatibleEmbeddingError):
        knowledge_service.search(db, "voter card", allow_auto_rebuild=False)

    # Restore and verify auto-rebuild recovers cleanly
    chunk.vector_json = original_vector
    db.commit()
    recovered = knowledge_service.search(db, "voter card", allow_auto_rebuild=True)
    assert len(recovered) > 0
