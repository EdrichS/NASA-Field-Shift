export const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'hi', label: 'हिन्दी' },
  { value: 'sw', label: 'Kiswahili' },
  { value: 'pt', label: 'Português' },
  { value: 'tl', label: 'Tagalog' },
] as const

export type LanguageCode = (typeof LANGUAGES)[number]['value']

const en = {
  disclaimerTitle: 'Language',
  languageLabel: 'Preferred language',
  noticeTitle: 'Translation & Language Notice',
  noticeBody:
    'Automated translations in SowSmart may not always be 100% accurate, especially for specialized farming or local crop terms. Always double-check critical planting or input measurements.',
  reportWarning:
    'Reports are most reliable in English. In other languages the quality may be lower, and some words will stay in English when there is no common local word for them.',
  acknowledge:
    'I understand that translations may not always be accurate and wish to continue in my selected language.',
  continue: 'Continue',
  back: 'Back',
  home: 'Home',
  fields: 'Fields',
  plan: 'Plan',
  alerts: 'Alerts',
  welcome: 'Welcome, {name}',
  yourFarm: 'Your farm',
  planTitle: 'Farm plan',
  planBody: 'Your planting plan will show up here when it is ready. Nothing has been saved on a server.',
  fieldTitle: 'Field',
  coordinates: 'Pin',
  setupTitle: 'How you set up',
  pathQuick: 'Quick 5',
  pathDetailed: 'Detailed profile',
  pathExplore: 'Just exploring',
  nextTitle: 'Next steps',
  nextCompare: 'Compare this season with other rotations',
  nextWater: 'Check water and the months the field sits empty',
  nextExpert: 'Ask a local expert before you plant',
  alertsEmpty: 'No alerts yet. Alerts for a saved field come later.',
  fieldsHint: 'This is the pin from setup. A field boundary can be added later.',
  planHint: 'Sow Smart has not generated a plan yet. Your answers stay in this browser.',
  showing: 'This screen is in {language}.',
}

const es: typeof en = {
  disclaimerTitle: 'Idioma',
  languageLabel: 'Idioma preferido',
  noticeTitle: 'Aviso de traducción e idioma',
  noticeBody:
    'Las traducciones automáticas de SowSmart pueden no ser siempre 100% precisas, sobre todo en términos de agricultura o de cultivos locales. Revise siempre las medidas críticas de siembra o de insumos.',
  reportWarning:
    'Los informes son más confiables en inglés. En otros idiomas la calidad puede ser menor, y algunas palabras se quedan en inglés cuando no hay un término local común.',
  acknowledge:
    'Entiendo que las traducciones pueden no ser siempre precisas y deseo continuar en el idioma que elegí.',
  continue: 'Continuar',
  back: 'Atrás',
  home: 'Inicio',
  fields: 'Parcelas',
  plan: 'Plan',
  alerts: 'Alertas',
  welcome: 'Bienvenido, {name}',
  yourFarm: 'Su finca',
  planTitle: 'Plan de la finca',
  planBody: 'Su plan de siembra aparecerá aquí cuando esté listo. No se ha guardado nada en un servidor.',
  fieldTitle: 'Parcela',
  coordinates: 'Punto',
  setupTitle: 'Cómo lo configuró',
  pathQuick: '5 preguntas rápidas',
  pathDetailed: 'Perfil detallado',
  pathExplore: 'Solo explorando',
  nextTitle: 'Próximos pasos',
  nextCompare: 'Compare esta temporada con otras rotaciones',
  nextWater: 'Revise el agua y los meses sin cultivo',
  nextExpert: 'Consulte a un experto local antes de sembrar',
  alertsEmpty: 'Aún no hay alertas. Las alertas de una parcela guardada llegan después.',
  fieldsHint: 'Este es el punto del registro. El límite de la parcela se puede añadir después.',
  planHint: 'Sow Smart todavía no ha generado un plan. Sus respuestas quedan en este navegador.',
  showing: 'Esta pantalla está en {language}.',
}

const fr: typeof en = {
  disclaimerTitle: 'Langue',
  languageLabel: 'Langue préférée',
  noticeTitle: 'Avis de traduction et de langue',
  noticeBody:
    'Les traductions automatiques de SowSmart ne sont pas toujours exactes à 100 %, surtout pour les termes agricoles ou les cultures locales. Vérifiez toujours les mesures importantes de semis ou d’intrants.',
  reportWarning:
    'Les rapports sont plus fiables en anglais. Dans les autres langues, la qualité peut être moindre, et certains mots restent en anglais lorsqu’il n’existe pas de terme local courant.',
  acknowledge:
    'Je comprends que les traductions ne sont pas toujours exactes et je souhaite continuer dans la langue choisie.',
  continue: 'Continuer',
  back: 'Retour',
  home: 'Accueil',
  fields: 'Parcelles',
  plan: 'Plan',
  alerts: 'Alertes',
  welcome: 'Bienvenue, {name}',
  yourFarm: 'Votre ferme',
  planTitle: 'Plan de la ferme',
  planBody: 'Votre plan de semis s’affichera ici lorsqu’il sera prêt. Rien n’a été enregistré sur un serveur.',
  fieldTitle: 'Parcelle',
  coordinates: 'Point',
  setupTitle: 'Votre parcours',
  pathQuick: '5 questions rapides',
  pathDetailed: 'Profil détaillé',
  pathExplore: 'Simple exploration',
  nextTitle: 'Prochaines étapes',
  nextCompare: 'Comparez cette saison avec d’autres rotations',
  nextWater: 'Vérifiez l’eau et les mois sans culture',
  nextExpert: 'Demandez à un expert local avant de semer',
  alertsEmpty: 'Pas encore d’alerte. Les alertes d’une parcelle enregistrée viendront plus tard.',
  fieldsHint: 'Voici le point choisi à l’inscription. Le contour de la parcelle pourra être ajouté ensuite.',
  planHint: 'Sow Smart n’a pas encore généré de plan. Vos réponses restent dans ce navigateur.',
  showing: 'Cet écran est en {language}.',
}

const hi: typeof en = {
  disclaimerTitle: 'भाषा',
  languageLabel: 'पसंदीदा भाषा',
  noticeTitle: 'अनुवाद और भाषा सूचना',
  noticeBody:
    'SowSmart के स्वचालित अनुवाद हमेशा 100% सटीक नहीं होते, खासकर खेती या स्थानीय फसल के शब्दों में। बुवाई या इनपुट की महत्वपूर्ण माप हमेशा दोबारा जाँचें।',
  reportWarning:
    'रिपोर्ट अंग्रेज़ी में सबसे भरोसेमंद होती हैं। अन्य भाषाओं में गुणवत्ता कम हो सकती है, और जब कोई आम स्थानीय शब्द नहीं होता तो कुछ शब्द अंग्रेज़ी में रह जाते हैं।',
  acknowledge:
    'मैं समझता हूँ कि अनुवाद हमेशा सटीक नहीं होते और मैं चुनी हुई भाषा में आगे बढ़ना चाहता हूँ।',
  continue: 'आगे बढ़ें',
  back: 'वापस',
  home: 'होम',
  fields: 'खेत',
  plan: 'योजना',
  alerts: 'चेतावनियाँ',
  welcome: 'स्वागत है, {name}',
  yourFarm: 'आपका खेत',
  planTitle: 'खेत की योजना',
  planBody: 'आपकी बुवाई योजना तैयार होने पर यहाँ दिखेगी। सर्वर पर कुछ सहेजा नहीं गया है।',
  fieldTitle: 'खेत',
  coordinates: 'पिन',
  setupTitle: 'आपने कैसे सेट किया',
  pathQuick: '5 तेज़ प्रश्न',
  pathDetailed: 'विस्तृत प्रोफ़ाइल',
  pathExplore: 'अभी देख रहे हैं',
  nextTitle: 'अगले कदम',
  nextCompare: 'इस मौसम की तुलना अन्य फसल चक्रों से करें',
  nextWater: 'पानी और खाली महीने जाँचें',
  nextExpert: 'बोने से पहले स्थानीय विशेषज्ञ से पूछें',
  alertsEmpty: 'अभी कोई चेतावनी नहीं है। सहेजे खेत की चेतावनियाँ बाद में आएँगी।',
  fieldsHint: 'यह सेटअप का पिन है। खेत की सीमा बाद में जोड़ी जा सकती है।',
  planHint: 'Sow Smart ने अभी योजना नहीं बनाई है। आपके जवाब इसी ब्राउज़र में रहते हैं।',
  showing: 'यह स्क्रीन {language} में है।',
}

const sw: typeof en = {
  disclaimerTitle: 'Lugha',
  languageLabel: 'Lugha unayopendelea',
  noticeTitle: 'Taarifa ya tafsiri na lugha',
  noticeBody:
    'Tafsiri za kiotomatiki za SowSmart huenda zisiwe sahihi kwa asilimia 100 kila wakati, hasa kwa maneno ya kilimo au mazao ya kienyeji. Kagua tena vipimo muhimu vya kupanda au pembejeo.',
  reportWarning:
    'Ripoti ni za kuaminika zaidi kwa Kiingereza. Katika lugha nyingine ubora unaweza kuwa chini, na baadhi ya maneno hubaki kwa Kiingereza ikiwa hakuna neno la kawaida la kienyeji.',
  acknowledge:
    'Ninaelewa kuwa tafsiri huenda zisiwe sahihi kila wakati na nataka kuendelea kwa lugha niliyochagua.',
  continue: 'Endelea',
  back: 'Rudi',
  home: 'Nyumbani',
  fields: 'Mashamba',
  plan: 'Mpango',
  alerts: 'Tahadhari',
  welcome: 'Karibu, {name}',
  yourFarm: 'Shamba lako',
  planTitle: 'Mpango wa shamba',
  planBody: 'Mpango wako wa upandaji utaonekana hapa utakapokuwa tayari. Hakuna kilichohifadhiwa kwenye seva.',
  fieldTitle: 'Shamba',
  coordinates: 'Nukta',
  setupTitle: 'Jinsi ulivyosanidi',
  pathQuick: 'Maswali 5 ya haraka',
  pathDetailed: 'Wasifu wa kina',
  pathExplore: 'Kuangalia tu',
  nextTitle: 'Hatua zinazofuata',
  nextCompare: 'Linganisha msimu huu na mzunguko mwingine',
  nextWater: 'Kagua maji na miezi bila mazao',
  nextExpert: 'Uliza mtaalamu wa eneo kabla ya kupanda',
  alertsEmpty: 'Bado hakuna tahadhari. Tahadhari za shamba lililohifadhiwa zinakuja baadaye.',
  fieldsHint: 'Hii ndiyo nukta kutoka kwenye usanidi. Mpaka wa shamba unaweza kuongezwa baadaye.',
  planHint: 'Sow Smart bado haijatengeneza mpango. Majibu yako yanabaki kwenye kivinjari hiki.',
  showing: 'Skrini hii iko kwa {language}.',
}

const pt: typeof en = {
  disclaimerTitle: 'Idioma',
  languageLabel: 'Idioma preferido',
  noticeTitle: 'Aviso de tradução e idioma',
  noticeBody:
    'As traduções automáticas do SowSmart podem não ser sempre 100% precisas, sobretudo em termos agrícolas ou de culturas locais. Confira sempre as medidas críticas de plantio ou de insumos.',
  reportWarning:
    'Os relatórios são mais confiáveis em inglês. Em outros idiomas a qualidade pode ser menor, e algumas palavras ficam em inglês quando não há um termo local comum.',
  acknowledge:
    'Entendo que as traduções podem não ser sempre precisas e quero continuar no idioma que escolhi.',
  continue: 'Continuar',
  back: 'Voltar',
  home: 'Início',
  fields: 'Talhões',
  plan: 'Plano',
  alerts: 'Alertas',
  welcome: 'Bem-vindo, {name}',
  yourFarm: 'Sua fazenda',
  planTitle: 'Plano da fazenda',
  planBody: 'Seu plano de plantio aparecerá aqui quando estiver pronto. Nada foi salvo em um servidor.',
  fieldTitle: 'Talhão',
  coordinates: 'Ponto',
  setupTitle: 'Como você configurou',
  pathQuick: '5 perguntas rápidas',
  pathDetailed: 'Perfil detalhado',
  pathExplore: 'Só explorando',
  nextTitle: 'Próximos passos',
  nextCompare: 'Compare esta safra com outras rotações',
  nextWater: 'Verifique a água e os meses sem cultivo',
  nextExpert: 'Pergunte a um especialista local antes de plantar',
  alertsEmpty: 'Ainda não há alertas. Os alertas de um talhão salvo vêm depois.',
  fieldsHint: 'Este é o ponto do cadastro. O limite do talhão pode ser acrescentado depois.',
  planHint: 'O Sow Smart ainda não gerou um plano. Suas respostas ficam neste navegador.',
  showing: 'Esta tela está em {language}.',
}

const tl: typeof en = {
  disclaimerTitle: 'Wika',
  languageLabel: 'Gustong wika',
  noticeTitle: 'Paunawa sa salin at wika',
  noticeBody:
    'Maaaring hindi laging 100% tumpak ang awtomatikong salin sa SowSmart, lalo na sa mga tuntunin ng pagsasaka o lokal na pananim. Laging suriin ang mahahalagang sukat sa pagtatanim o mga input.',
  reportWarning:
    'Pinaka-maaasahan ang mga ulat sa Ingles. Sa ibang wika maaaring mas mababa ang kalidad, at mananatili sa Ingles ang ilang salita kapag walang karaniwang lokal na katumbas.',
  acknowledge:
    'Nauunawaan ko na maaaring hindi laging tumpak ang mga salin at nais kong magpatuloy sa wikang pinili ko.',
  continue: 'Magpatuloy',
  back: 'Bumalik',
  home: 'Tahanan',
  fields: 'Mga bukid',
  plan: 'Plano',
  alerts: 'Mga alerto',
  welcome: 'Maligayang pagdating, {name}',
  yourFarm: 'Ang iyong bukid',
  planTitle: 'Plano ng bukid',
  planBody: 'Lalabas dito ang plano ng pagtatanim kapag handa na. Walang na-save sa server.',
  fieldTitle: 'Bukid',
  coordinates: 'Pin',
  setupTitle: 'Paano ka nag-set up',
  pathQuick: '5 mabilis na tanong',
  pathDetailed: 'Detalyadong profile',
  pathExplore: 'Tumitingin lang',
  nextTitle: 'Susunod na hakbang',
  nextCompare: 'Ihambing ang panahong ito sa ibang rotasyon',
  nextWater: 'Suriin ang tubig at mga buwang walang pananim',
  nextExpert: 'Magtanong sa lokal na dalubhasa bago magtanim',
  alertsEmpty: 'Wala pang alerto. Ang mga alerto para sa naka-save na bukid ay susunod pa.',
  fieldsHint: 'Ito ang pin mula sa setup. Maaaring idagdag ang hangganan ng bukid mamaya.',
  planHint: 'Hindi pa gumagawa ng plano ang Sow Smart. Nanatili sa browser na ito ang iyong mga sagot.',
  showing: 'Ang screen na ito ay nasa {language}.',
}

const DICT: Record<LanguageCode, typeof en> = { en, es, fr, hi, sw, pt, tl }

export type MessageKey = keyof typeof en

export function isLanguage(value: string): value is LanguageCode {
  return LANGUAGES.some((item) => item.value === value)
}

export function languageLabel(code: LanguageCode) {
  return LANGUAGES.find((item) => item.value === code)?.label ?? 'English'
}

export function translate(language: LanguageCode, key: MessageKey, vars?: Record<string, string>) {
  let text: string = DICT[language][key]
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, value)
    }
  }
  return text
}
