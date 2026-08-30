from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards.main import main_menu


router = Router()


class OnboardingStates(StatesGroup):
    question_1 = State()
    question_2 = State()
    question_3 = State()
    question_4 = State()
    question_5 = State()
    question_6 = State()
    question_7 = State()
    question_8 = State()
    question_9 = State()
    question_10 = State()


QUESTIONS = [
    "👤 <b>1/10</b>\n\nIsmingiz nima?",
    
    "🎂 <b>2/10</b>\n\nYoshingiz nechada?",
    
    "💼 <b>3/10</b>\n\nKasbingiz nima?",
    
    "🏢 <b>4/10</b>\n\nAsosan nima ish bilan shug‘ullanasiz?",
    
    "👥 <b>5/10</b>\n\nOdatda sizga kimlar yozadi?\n\n"
    "Masalan: talabalar, mijozlar, hamkasblar, do‘stlar, "
    "ota-onalar yoki hamkorlar.",
    
    "💬 <b>6/10</b>\n\nUlar sizga ko‘pincha nima sababdan yozishadi?",
    
    "📌 <b>7/10</b>\n\nSiz haqingizda Nano-Bot bilishi kerak bo‘lgan "
    "eng muhim ma’lumotlarni yozing.",
    
    "🗣 <b>8/10</b>\n\nOdamlar bilan qanday muloqot qilishni yoqtirasiz?\n\n"
    "Masalan: do‘stona, professional, rasmiy, qisqa va aniq, "
    "erkin yoki boshqa uslub.",
    
    "✅ <b>9/10</b>\n\nNano-Bot qaysi mavzularda sizning nomingizdan "
    "avtomatik javob berishi mumkin?",
    
    "🚫 <b>10/10</b>\n\nQaysi mavzularda Nano-Bot avtomatik javob "
    "bermasligi kerak va suhbatni sizga topshirishi kerak?",
]


STATES = [
    OnboardingStates.question_1,
    OnboardingStates.question_2,
    OnboardingStates.question_3,
    OnboardingStates.question_4,
    OnboardingStates.question_5,
    OnboardingStates.question_6,
    OnboardingStates.question_7,
    OnboardingStates.question_8,
    OnboardingStates.question_9,
    OnboardingStates.question_10,
]


async def start_onboarding(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🧠 <b>Nano-Bot sizni o‘rganadi</b>\n\n"
        "Avtomatik javoblar sizning faoliyatingiz va "
        "muloqot uslubingizga mos bo‘lishi uchun "
        "10 ta qisqa savolga javob bering.\n\n"
        "⏱ Bu taxminan 2–3 daqiqa vaqt oladi."
    )

    await state.set_state(OnboardingStates.question_1)

    await message.answer(QUESTIONS[0])


async def save_answer_and_continue(
    message: Message,
    state: FSMContext,
    question_number: int,
) -> None:
    answer = message.text.strip()

    if not answer:
        await message.answer(
            "⚠️ Iltimos, javob yozing."
        )
        return

    await state.update_data(
        **{
            f"question_{question_number}": answer
        }
    )

    next_number = question_number + 1

    if next_number <= 10:
        await state.set_state(STATES[next_number - 1])

        await message.answer(
            QUESTIONS[next_number - 1]
        )

        return

    data = await state.get_data()

    summary = (
        "🎉 <b>So‘rovnoma yakunlandi!</b>\n\n"
        "🧠 Nano-Bot siz haqingizdagi ma’lumotlarni qabul qildi.\n\n"
        "Endi keyingi bosqichda Telegram akkauntingizni "
        "ulashingiz va avtomatik javoblarni sozlashingiz mumkin.\n\n"
        "📋 <b>Sizning profilingiz:</b>\n\n"
        f"👤 Ism: {data.get('question_1', '-')}\n"
        f"🎂 Yosh: {data.get('question_2', '-')}\n"
        f"💼 Kasb: {data.get('question_3', '-')}\n"
        f"🏢 Faoliyat: {data.get('question_4', '-')}\n"
        f"👥 Auditoriya: {data.get('question_5', '-')}\n"
        f"💬 Murojaatlar: {data.get('question_6', '-')}\n"
        f"📌 Ma’lumot: {data.get('question_7', '-')}\n"
        f"🗣 Uslub: {data.get('question_8', '-')}\n"
        f"✅ Ruxsat etilgan mavzular: "
        f"{data.get('question_9', '-')}\n"
        f"🚫 Cheklangan mavzular: "
        f"{data.get('question_10', '-')}\n\n"
        "👇 Davom etish uchun menyudan foydalaning."
    )

    await message.answer(
        summary,
        reply_markup=main_menu(),
    )

    await state.clear()


@router.callback_query(F.data == "start_onboarding")
async def onboarding_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()

    await start_onboarding(
        callback.message,
        state,
    )


@router.message(OnboardingStates.question_1)
async def question_1(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        1,
    )


@router.message(OnboardingStates.question_2)
async def question_2(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        2,
    )


@router.message(OnboardingStates.question_3)
async def question_3(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        3,
    )


@router.message(OnboardingStates.question_4)
async def question_4(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        4,
    )


@router.message(OnboardingStates.question_5)
async def question_5(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        5,
    )


@router.message(OnboardingStates.question_6)
async def question_6(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        6,
    )


@router.message(OnboardingStates.question_7)
async def question_7(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        7,
    )


@router.message(OnboardingStates.question_8)
async def question_8(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        8,
    )


@router.message(OnboardingStates.question_9)
async def question_9(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        9,
    )


@router.message(OnboardingStates.question_10)
async def question_10(
    message: Message,
    state: FSMContext,
) -> None:
    await save_answer_and_continue(
        message,
        state,
        10,
    )