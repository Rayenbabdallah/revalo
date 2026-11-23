# ruff: noqa: E501  (catalog entries are whole sentences)
"""Text the server writes for people (decision reasons, alerts, errors), in English,
French or Arabic.

The English text is the key: code reads naturally and anything missing from a
catalog falls back to English. The language comes from the request's
Accept-Language header and lives in a context variable, so the engine and the
services need no extra arguments. Without a request (tests, CLI) it is English.
"""

from __future__ import annotations

from contextvars import ContextVar

SUPPORTED = ("en", "fr", "ar")
_lang: ContextVar[str] = ContextVar("revalo_lang", default="en")


def parse_accept_language(header: str | None) -> str:
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in SUPPORTED:
            return code
    return "en"


def set_lang(code: str):
    return _lang.set(code if code in SUPPORTED else "en")


def reset_lang(token) -> None:
    _lang.reset(token)


def lang() -> str:
    return _lang.get()


def num(value: float, digits: int = 1) -> str:
    """A number as people write it: 1,234.5 in English, 1 234,5 in French."""
    text = f"{value:,.{digits}f}"
    if lang() == "fr":
        return text.replace(",", " ").replace(".", ",")
    return text


def tr(template: str, **params: object) -> str:
    text = CATALOG.get(lang(), {}).get(template, template)
    if isinstance(text, dict):
        text = text.get("other", template)
    return text.format(**params) if params else text


def _arabic_form(n: int) -> str:
    if n == 0:
        return "zero"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 99:
        return "many"
    return "other"


def trn(template: str, count: int, **params: object) -> str:
    """Plural text. `template` is "one form|other form"; `{count}` is filled in."""
    entry = CATALOG.get(lang(), {}).get(template, template)
    if isinstance(entry, dict):
        text = entry.get(_arabic_form(count)) or entry.get("other", template)
    else:
        one, _, other = entry.partition("|")
        is_one = count in (0, 1) if lang() == "fr" else count == 1
        text = one if is_one or not other else other
    return text.format(count=count, **params)


def material_name(mat) -> str:
    """A library material's name in the reader's language."""
    if lang() == "fr":
        return mat.name_fr
    if lang() == "ar":
        return MATERIAL_AR.get(mat.code, mat.name_en)
    return mat.name_en


# Material names for Arabic; English and French come from the materials library.
MATERIAL_AR = {
    "steel_mild": "فولاذ عادي",
    "steel_galvanized": "فولاذ مجلفن",
    "stainless_304": "فولاذ مقاوم للصدأ 304",
    "stainless_316": "فولاذ مقاوم للصدأ 316",
    "aluminium": "ألمنيوم",
    "copper": "نحاس",
    "brass": "نحاس أصفر",
    "mdf": "MDF",
    "hdf": "HDF",
    "plywood": "خشب رقائقي",
    "particleboard": "خشب حبيبي",
    "melamine_board": "لوح ميلامين",
    "osb": "OSB",
    "solid_pine": "خشب صنوبر",
    "solid_beech": "خشب زان",
    "pmma": "أكريليك",
}


CATALOG: dict[str, dict[str, str | dict[str, str]]] = {
    "fr": {
        # Decision options and reasons
        "Skeleton and slugs cannot be reused.": "Le squelette et les chutes ne se réutilisent pas.",
        "Sold by weight only.": "Vendu uniquement au poids.",
        "Sorted lot for a recycler.": "Lot trié pour un recycleur.",
        "The skeleton between parts only sells by weight, as one sorted lot.": "Le squelette entre les pièces se vend uniquement au poids, en un lot trié.",
        "{kg} kg at {price} TND/kg: {value}.": "{kg} kg à {price} TND/kg : {value}.",
        "Add the thickness or weight to compare the options in dinars. Until then, keep it for reuse.": "Ajoutez l'épaisseur ou le poids pour comparer les options en dinars. En attendant, gardez-la pour réemploi.",
        "Add a price for {material} to compare the options in dinars. Until then, keep it for reuse.": "Ajoutez un prix pour {material} pour comparer les options en dinars. En attendant, gardez-la pour réemploi.",
        "New material you do not have to buy.": "De la matière neuve que vous n'avez pas à acheter.",
        "At {share} of the new price, after {fee} commission.": "À {share} du prix du neuf, après {fee} de commission.",
        "Too narrow to sell (under {size} mm).": "Trop étroite pour la vente (moins de {size} mm).",
        "Scrap price by weight.": "Prix de la ferraille au poids.",
        "Reusing it saves buying {kg} kg of new {material}: about {value}.": "La réemployer évite d'acheter {kg} kg de {material} neuf : environ {value}.",
        "Its shorter side is {size} mm, so fewer parts fit: value counted at {share}.": "Son petit côté fait {size} mm, moins de pièces y tiennent : valeur comptée à {share}.",
        "Not reused in {days} days. Selling brings about {sell}, against {scrap} as scrap.": "Pas réemployée en {days} jours. La vendre rapporte environ {sell}, contre {scrap} en ferraille.",
        "Not reused or sold in time: send it to a recycler before it blocks rack space ({value}).": "Ni réemployée ni vendue à temps : envoyez-la au recycleur avant qu'elle n'encombre les racks ({value}).",
        "Too small to find a buyer; as scrap it brings {value}.": "Trop petite pour trouver un acheteur ; en ferraille elle rapporte {value}.",
        "{material} offcuts have no scrap value: offer it to artisans or makers, even at a discount.": "Les chutes de {material} n'ont pas de valeur en ferraille : proposez-la aux artisans, même à prix réduit.",
        "{material} offcuts have no scrap value and this piece is small: keep it for small parts.": "Les chutes de {material} n'ont pas de valeur en ferraille et cette pièce est petite : gardez-la pour de petites pièces.",
        "Avoids about {kg} kg CO₂ of new material production.": "Évite environ {kg} kg de CO₂ de production de matière neuve.",
        "Recycling avoids about {kg} kg CO₂.": "Le recyclage évite environ {kg} kg de CO₂.",
        "this material": "ce matériau",
        # Alerts
        "Job waiting for review": "Travail en attente de vérification",
        "{file}: check and approve its leftover records.": "{file} : vérifiez et approuvez ses fiches de chutes.",
        "{count} piece past review date|{count} pieces past review date": "{count} pièce a dépassé sa date de revue|{count} pièces ont dépassé leur date de revue",
        "Not reused in time: now recommended for sale or recycling.": "Pas réemployées à temps : vente ou recyclage recommandés.",
        "{count} buyer for {code}|{count} buyers for {code}": "{count} acheteur pour {code}|{count} acheteurs pour {code}",
        "Best match: {name}, score {score}.": "Meilleure correspondance : {name}, score {score}.",
        "{kg} kg ready for a recycler": "{kg} kg prêts pour un recycleur",
        "{count} piece to send as a sorted lot.|{count} pieces to send as a sorted lot.": "{count} pièce à envoyer en lot trié.|{count} pièces à envoyer en lot trié.",
        "Pickup to schedule with {name}": "Enlèvement à planifier avec {name}",
        "{kg} kg requested; set the date when they reply.": "{kg} kg demandés ; fixez la date à leur réponse.",
        "{count} new buyer request|{count} new buyer requests": "{count} nouvelle demande d'acheteur|{count} nouvelles demandes d'acheteurs",
        # Errors people see
        "Sign in to continue.": "Connectez-vous pour continuer.",
        "Only a manager or above can do this.": "Seul un responsable ou plus peut faire cela.",
        "Only a owner or above can do this.": "Seul un propriétaire peut faire cela.",
        "Only a operator or above can do this.": "Connectez-vous pour continuer.",
        "Wrong email or password.": "E-mail ou mot de passe incorrect.",
        "Too many tries. Wait a few minutes and try again.": "Trop de tentatives. Attendez quelques minutes et réessayez.",
        "This workshop is already set up. Sign in instead.": "Cet atelier est déjà configuré. Connectez-vous.",
        "Use at least 8 characters for the password.": "Utilisez au moins 8 caractères pour le mot de passe.",
        "That password is too long.": "Ce mot de passe est trop long.",
        "Enter a valid email address.": "Entrez une adresse e-mail valide.",
        "Enter the person's name.": "Entrez le nom de la personne.",
        "Someone already has an account with this email.": "Quelqu'un a déjà un compte avec cet e-mail.",
        "The workshop needs at least one active owner.": "L'atelier doit garder au moins un propriétaire actif.",
        "The current password is not right.": "Le mot de passe actuel n'est pas correct.",
        "No such person in this workshop.": "Cette personne n'est pas dans l'atelier.",
        "File is larger than 25 MB.": "Le fichier dépasse 25 Mo.",
        "The file took too long to analyze.": "L'analyse du fichier a pris trop de temps.",
        "Piece not found.": "Pièce introuvable.",
        "Job not found.": "Travail introuvable.",
        "No piece with this code.": "Aucune pièce avec ce code.",
        "Unknown machine.": "Machine inconnue.",
    },
    "ar": {
        "Skeleton and slugs cannot be reused.": "الهيكل والقطع الصغيرة لا يُعاد استعمالها.",
        "Sold by weight only.": "يُباع بالوزن فقط.",
        "Sorted lot for a recycler.": "دفعة مفروزة لمُعيد التدوير.",
        "The skeleton between parts only sells by weight, as one sorted lot.": "الهيكل بين القطع يُباع بالوزن فقط، كدفعة واحدة مفروزة.",
        "{kg} kg at {price} TND/kg: {value}.": "{kg} kg بسعر {price} TND/kg: {value}.",
        "Add the thickness or weight to compare the options in dinars. Until then, keep it for reuse.": "أضف السُمك أو الوزن لمقارنة الخيارات بالدينار. إلى ذلك الحين، احتفظ بها لإعادة الاستعمال.",
        "Add a price for {material} to compare the options in dinars. Until then, keep it for reuse.": "أضف سعرًا لـ{material} لمقارنة الخيارات بالدينار. إلى ذلك الحين، احتفظ بها لإعادة الاستعمال.",
        "New material you do not have to buy.": "مادة جديدة لن تحتاج إلى شرائها.",
        "At {share} of the new price, after {fee} commission.": "بـ{share} من سعر الجديد، بعد عمولة {fee}.",
        "Too narrow to sell (under {size} mm).": "ضيقة جدًا للبيع (أقل من {size} mm).",
        "Scrap price by weight.": "سعر الخردة بالوزن.",
        "Reusing it saves buying {kg} kg of new {material}: about {value}.": "إعادة استعمالها توفّر شراء {kg} kg من {material} الجديد: حوالي {value}.",
        "Its shorter side is {size} mm, so fewer parts fit: value counted at {share}.": "ضلعها الأقصر {size} mm، فتتسع لقطع أقل: القيمة محسوبة بـ{share}.",
        "Not reused in {days} days. Selling brings about {sell}, against {scrap} as scrap.": "لم يُعَد استعمالها خلال {days} يومًا. البيع يجلب حوالي {sell}، مقابل {scrap} كخردة.",
        "Not reused or sold in time: send it to a recycler before it blocks rack space ({value}).": "لم يُعَد استعمالها ولم تُبَع في الوقت: أرسلها إلى مُعيد التدوير قبل أن تشغل الرفوف ({value}).",
        "Too small to find a buyer; as scrap it brings {value}.": "صغيرة جدًا لإيجاد مشترٍ؛ كخردة تجلب {value}.",
        "{material} offcuts have no scrap value: offer it to artisans or makers, even at a discount.": "بقايا {material} ليس لها قيمة كخردة: اعرضها على الحرفيين، ولو بتخفيض.",
        "{material} offcuts have no scrap value and this piece is small: keep it for small parts.": "بقايا {material} ليس لها قيمة كخردة وهذه القطعة صغيرة: احتفظ بها للقطع الصغيرة.",
        "Avoids about {kg} kg CO₂ of new material production.": "تتجنّب حوالي {kg} kg من CO₂ لإنتاج مادة جديدة.",
        "Recycling avoids about {kg} kg CO₂.": "إعادة التدوير تتجنّب حوالي {kg} kg من CO₂.",
        "this material": "هذه المادة",
        "Job waiting for review": "عمل في انتظار المراجعة",
        "{file}: check and approve its leftover records.": "{file}: راجع سجلات البقايا ووافق عليها.",
        "{count} piece past review date|{count} pieces past review date": {
            "one": "قطعة واحدة تجاوزت تاريخ المراجعة",
            "two": "قطعتان تجاوزتا تاريخ المراجعة",
            "few": "{count} قطع تجاوزت تاريخ المراجعة",
            "other": "{count} قطعة تجاوزت تاريخ المراجعة",
        },
        "Not reused in time: now recommended for sale or recycling.": "لم يُعَد استعمالها في الوقت: يُنصح الآن ببيعها أو إعادة تدويرها.",
        "{count} buyer for {code}|{count} buyers for {code}": {
            "one": "مشترٍ واحد لـ{code}",
            "two": "مشتريان لـ{code}",
            "few": "{count} مشترين لـ{code}",
            "other": "{count} مشتريًا لـ{code}",
        },
        "Best match: {name}, score {score}.": "أفضل تطابق: {name}، النقاط {score}.",
        "{kg} kg ready for a recycler": "{kg} kg جاهزة لمُعيد التدوير",
        "{count} piece to send as a sorted lot.|{count} pieces to send as a sorted lot.": {
            "one": "قطعة واحدة لإرسالها كدفعة مفروزة.",
            "two": "قطعتان لإرسالهما كدفعة مفروزة.",
            "few": "{count} قطع لإرسالها كدفعة مفروزة.",
            "other": "{count} قطعة لإرسالها كدفعة مفروزة.",
        },
        "Pickup to schedule with {name}": "استلام يجب برمجته مع {name}",
        "{kg} kg requested; set the date when they reply.": "{kg} kg مطلوبة؛ حدّد الموعد عند ردّهم.",
        "{count} new buyer request|{count} new buyer requests": {
            "one": "طلب شراء جديد",
            "two": "طلبا شراء جديدان",
            "few": "{count} طلبات شراء جديدة",
            "other": "{count} طلب شراء جديد",
        },
        "Sign in to continue.": "سجّل الدخول للمتابعة.",
        "Only a manager or above can do this.": "هذا متاح للمسؤول أو المالك فقط.",
        "Only a owner or above can do this.": "هذا متاح للمالك فقط.",
        "Only a operator or above can do this.": "سجّل الدخول للمتابعة.",
        "Wrong email or password.": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "Too many tries. Wait a few minutes and try again.": "محاولات كثيرة. انتظر بضع دقائق ثم أعد المحاولة.",
        "This workshop is already set up. Sign in instead.": "هذه الورشة مُعدّة مسبقًا. سجّل الدخول.",
        "Use at least 8 characters for the password.": "استعمل 8 أحرف على الأقل لكلمة المرور.",
        "That password is too long.": "كلمة المرور طويلة جدًا.",
        "Enter a valid email address.": "أدخل بريدًا إلكترونيًا صحيحًا.",
        "Enter the person's name.": "أدخل اسم الشخص.",
        "Someone already has an account with this email.": "يوجد حساب بهذا البريد الإلكتروني.",
        "The workshop needs at least one active owner.": "تحتاج الورشة إلى مالك نشط واحد على الأقل.",
        "The current password is not right.": "كلمة المرور الحالية غير صحيحة.",
        "No such person in this workshop.": "هذا الشخص ليس في الورشة.",
        "File is larger than 25 MB.": "الملف أكبر من 25 ميغابايت.",
        "The file took too long to analyze.": "استغرق تحليل الملف وقتًا طويلًا.",
        "Piece not found.": "القطعة غير موجودة.",
        "Job not found.": "العمل غير موجود.",
        "No piece with this code.": "لا توجد قطعة بهذا الرمز.",
        "Unknown machine.": "آلة غير معروفة.",
    },
}
