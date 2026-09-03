from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import TermsAcceptance

TERMS_VERSION = "1.1"

TERMS_GATE_TEXT = (
    "🔐 <b>NANO-BOT FOYDALANISH SHARTLARI</b>\n\n"
    "Nano-Bot — Telegram akkauntini avtomatlashtirish uchun "
    "mo‘ljallangan mustaqil texnik xizmat.\n\n"
    "Telegram akkauntingizni ulashdan oldin, iltimos, "
    "foydalanish shartlari bilan tanishib chiqing va rozilik "
    "bildiring."
)

_TERMS_SECTIONS: List[str] = [
    (
        "<b>1. UMUMIY QOIDALAR</b>\n"
        "• Nano-Bot — mustaqil texnik avtomatlashtirish xizmati "
        "bo‘lib, foydalanuvchining shaxsiy Telegram akkauntiga "
        "ma’lum avtomatlashtirish funksiyalarini (Auto Reply, "
        "First Message va h.k.) taqdim etadi.\n"
        "• Nano-Bot biror davlat tashkiloti, davlat organi, "
        "davlat korxonasi yoki davlat muassasasi nomidan "
        "ishlamaydi va ularga tegishli emas.\n"
        "• Nano-Bot o‘zini alohida rasmiy tijorat tashkiloti "
        "sifatida taqdim etmaydi — bu mustaqil dasturiy xizmat.\n"
        "• Kelajakda xizmat doirasida pullik (Premium) "
        "funksiyalar joriy etilishi mumkin; bunday holatda "
        "foydalanuvchilar alohida xabardor qilinadi."
    ),
    (
        "<b>2. TELEGRAM AKKAUNTI</b>\n"
        "• Foydalanuvchi faqat o‘ziga tegishli yoki foydalanish "
        "uchun qonuniy huquqqa ega bo‘lgan Telegram akkauntini "
        "ulashi shart.\n"
        "• Boshqa shaxsga tegishli akkauntni ruxsatsiz ulash "
        "qat’iyan taqiqlanadi.\n"
        "• Ulangan Telegram akkaunti orqali amalga oshirilgan "
        "barcha harakatlar uchun javobgarlik to‘liq "
        "foydalanuvchi zimmasida bo‘ladi."
    ),
    (
        "<b>3. AVTOMATLASHTIRISH</b>\n"
        "• Auto Reply va First Message funksiyalari to‘liq "
        "foydalanuvchi tomonidan sozlanadi.\n"
        "• Yuboriladigan kontent va kalit so‘zlar mazmuni uchun "
        "javobgarlik foydalanuvchida.\n"
        "• Spam, firibgarlik, noqonuniy kontent tarqatish yoki "
        "boshqa zararli maqsadlarda avtomatlashtirishdan "
        "foydalanish qat’iyan taqiqlanadi.\n"
        "• Telegram xizmat ko‘rsatish shartlariga zid har "
        "qanday foydalanish taqiqlanadi va bunday holatlarda "
        "xizmat ko‘rsatish to‘xtatilishi mumkin."
    ),
    (
        "<b>4. AVTORIZATSIYA VA SESSION</b>\n"
        "• Telegram hisobga kirish jarayonida yuboriladigan "
        "tasdiqlash kodi (OTP) va ikki bosqichli himoya (2FA) "
        "paroli faqat avtorizatsiya jarayonining o‘zida "
        "ishlatiladi.\n"
        "• OTP va 2FA parollari bazada saqlanmaydi.\n"
        "• Xizmatning ishlashi uchun zarur bo‘lgan Telegram "
        "session ma’lumotlari saqlanishi mumkin — bu xizmatning "
        "texnik talabi.\n"
        "• Session ma’lumotlari maxfiy hisoblanadi va hech "
        "qachon jurnal (log) yozuvlarida ko‘rsatilmaydi."
    ),
    (
        "<b>5. MA’LUMOTLARNI QAYTA ISHLASH</b>\n"
        "• Xabarlar (chat) mazmuni doimiy saqlanmaydi.\n"
        "• Xizmatning ishlashi uchun zarur texnik ma’lumotlar "
        "(foydalanuvchi ID, ulangan Telegram akkaunt ID, "
        "Storage kanalidagi post havolasi, statistik "
        "ko‘rsatkichlar) saqlanishi mumkin.\n"
        "• Telegram akkauntining avtorizatsiya/session "
        "ma’lumotlari xizmat ishlashi uchun xavfsiz tarzda "
        "saqlanadi.\n"
        "• Auto Reply va First Message uchun media kontent "
        "bazada ikkilik (binary) ko‘rinishda saqlanmaydi — "
        "media alohida shaxsiy Storage Channel orqali "
        "boshqariladi.\n"
        "• <i>Ushbu band xizmat “hech qanday ma’lumotni "
        "saqlamaydi” degan ma’noni anglatmaydi</i> — yuqorida "
        "ko‘rsatilgan texnik ma’lumotlar xizmatning ishlashi "
        "uchun zarur va saqlanishi mumkin."
    ),
    (
        "<b>6. XAVFSIZLIK</b>\n"
        "• Xizmat foydalanuvchi ma’lumotlarini himoya qilish "
        "uchun oqilona texnik choralarni qo‘llaydi.\n"
        "• Shunga qaramay, hech qanday internet xizmati 100% "
        "xavfsizlikni kafolatlay olmaydi."
    ),
    (
        "<b>7. HUJUMLAR VA UCHINCHI TOMON HODISALARI</b>\n"
        "• Nano-Bot tasodifiy yoki maqsadli kiberhujumlarning "
        "oldini to‘liq olishni kafolatlamaydi.\n"
        "• Xizmat o‘z nazorati doirasidan tashqarida yuzaga "
        "keladigan uchinchi tomon hujumlari, Telegram "
        "infratuzilmasidagi uzilishlar yoki boshqa tashqi "
        "hodisalar uchun mutlaq javobgarlikni o‘z zimmasiga "
        "olmaydi.\n"
        "• Shunga qaramay, xavfsizlik hodisalarini aniqlash va "
        "imkon qadar tegishli choralarni ko‘rish (jumladan "
        "administratorni xabardor qilish) mexanizmlari mavjud."
    ),
    (
        "<b>8. FOYDALANUVCHI JAVOBGARLIGI</b>\n"
        "• Foydalanuvchi o‘z Telegram akkaunti orqali "
        "yuborilgan barcha xabarlar uchun mustaqil javobgar "
        "hisoblanadi.\n"
        "• Spam yoki noqonuniy faoliyat yuzaga kelgan taqdirda, "
        "bu Nano-Bot xizmatining javobgarligi deb hisoblanmaydi."
    ),
    (
        "<b>9. XIZMATNI TO‘XTATISH VA MA’LUMOTLARNI "
        "O‘CHIRISH</b>\n"
        "• Foydalanuvchi istalgan vaqtda Telegram akkauntini "
        "Nano-Botdan uzishi mumkin (📱 «Telegram ulash» → "
        "«🔌 Telegramni uzish»).\n"
        "• Akkaunt uzilganda, ulanish holati va Telegram "
        "session ma’lumotlari faolsizlantiriladi.\n"
        "• Foydalanuvchi o‘zi sozlagan Auto Reply va First "
        "Message yozuvlarini istalgan vaqtda botning tegishli "
        "menyusi orqali o‘zi o‘chirishi mumkin.\n"
        "• Foydalanuvchi barcha shaxsiy texnik ma’lumotlarini "
        "(profil, sozlamalar, statistikalar) o‘chirishni "
        "so‘rash uchun administratorga murojaat qilishi "
        "mumkin; bunday so‘rov qonuniy va texnik talablarga "
        "muvofiq amalga oshiriladi.\n"
        "• Xavfsizlik yoki texnik zarurat tug‘ilganda, "
        "administrator xizmatni vaqtincha to‘xtatishi mumkin.\n"
        "• Zarur bo‘lganda Telegram session bekor qilinishi "
        "(logout) uchun tegishli mexanizm mavjud."
    ),
    (
        "<b>10. QABUL QILISH</b>\n"
        "• “✅ Qabul qilaman” tugmasini bosish orqali "
        "foydalanuvchi ushbu shartlarni to‘liq o‘qigan va "
        "ularga rozi ekanligini tasdiqlaydi.\n"
        "• Shartlarni qabul qilmasdan Telegram akkauntini ulash "
        "jarayoni boshlanmaydi."
    ),
]


def _paginate_sections(
    sections: List[str],
    max_chars: int = 3000,
) -> List[str]:
    pages: List[str] = []
    current = ""

    for section in sections:
        candidate = (
            f"{current}\n\n{section}"
            if current
            else section
        )

        if len(candidate) > max_chars and current:
            pages.append(current)
            current = section
        else:
            current = candidate

    if current:
        pages.append(current)

    return pages


TERMS_PAGES: List[str] = _paginate_sections(_TERMS_SECTIONS)
TERMS_PAGE_COUNT = len(TERMS_PAGES)


def get_terms_page(index: int) -> str:
    index = max(0, min(index, TERMS_PAGE_COUNT - 1))

    header = (
        f"📄 <b>Nano-Bot foydalanish shartlari</b> "
        f"({index + 1}/{TERMS_PAGE_COUNT})\n\n"
    )

    return header + TERMS_PAGES[index]


# ============================================================
# DATABASE
# ============================================================

async def has_accepted_terms(
    user_id: int,
    version: str = TERMS_VERSION,
) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TermsAcceptance.id)
            .where(TermsAcceptance.user_id == user_id)
            .where(TermsAcceptance.terms_version == version)
            .limit(1)
        )

        return result.scalar_one_or_none() is not None


async def record_terms_acceptance(
    user_id: int,
    version: str = TERMS_VERSION,
) -> Optional[TermsAcceptance]:
    """
    Foydalanuvchi roziligini qayd etadi.

    Idempotent: bir xil versiya uchun qayta chaqirilsa,
    yangi qator yaratmaydi.
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TermsAcceptance)
            .where(TermsAcceptance.user_id == user_id)
            .where(TermsAcceptance.terms_version == version)
            .limit(1)
        )

        existing = result.scalar_one_or_none()

        if existing is not None:
            return existing

        acceptance = TermsAcceptance(
            user_id=user_id,
            terms_version=version,
        )

        session.add(acceptance)

        await session.commit()
        await session.refresh(acceptance)

        return acceptance


__all__ = [
    "TERMS_VERSION",
    "TERMS_GATE_TEXT",
    "TERMS_PAGE_COUNT",
    "get_terms_page",
    "has_accepted_terms",
    "record_terms_acceptance",
]
