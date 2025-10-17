import streamlit as st
import os
import json
import zipfile
import io
import uuid
import re
from datetime import datetime
from typing import List, Dict
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

DEFAULT_SYSTEM_PROMPT = """🧠 ПРОМПТ ДЛЯ ИИ-SMM-АГЕНТА

Цель: Генерировать вирусные карточки Threads в формате "Типы экспертов отвечают на любую проблему" в виде валидного JSON.

📄 Формат вывода - строго валидный JSON:
{
  "id": "<уникальный_идентификатор>",
  "theme": "<короткая тема / проблема>",
  "replies": [
    {
      "role": "<роль или тип говорящего>",
      "text": "<форматированный текст реплики>"
    }
  ],
  "cta": "<призыв к действию>",
  "tags": ["#тег1", "#тег2", "#тег3"],
  "language": "ru"
}

⚙️ Технические требования:
* Ответ строго JSON, без комментариев, без текста до или после
* replies содержит от 6 до 8 реплик
* Первая реплика — тема/проблема ("Я" или "Клиент")
* Последняя — панчлайн ("ФИНАЛ" или какой-нибудь персонаж/эксперт)
* Все роли уникальны внутри одного поста
* theme — короткая (1–4 слова)
* language всегда "ru"

🎭 Стиль и содержание:
* Тон: юмористический
* Настроение: меньше депрессии — больше иронии, сатиры, бытового абсурда
* Последняя реплика — панчлайн: короткая, неожиданная

Типы персонажей:
Выбирай экспертов/персонажей из жизни по заданной теме.
Используй разных “экспертов” в каждой реплике.
Можно добавлять абсурдные (“ДУХ {...}”, “Wi-Fi”, “ГОСУСЛУГИ”, “СОСЕД”).

✍️ Форматирование текста:
* жирный для эмоциональных слов
* *курсив* для подчеркивания
* Используй простой текст без HTML

🔥 Правила панчлайна:
* Последняя реплика короткая (1-3 строки)
* Может быть полностью капсом
* Обязательно выделить ключевое слово

📢 CTA (выбери один):
* "Укажи себя👇"

🏷️ Хештеги: 3–5 штук (#ирония, #threadsюмор, #психология, #мемы, #коучинг)

🚫 Без насилия, дискриминации, политики, откровенного контента."""

# ============================================       
# КЛАССЫ ДЛЯ ГЕНЕРАЦИИ
# ============================================

class ThreadsCardGenerator:
    """ИИ-агент для генерации вирусных карточек Threads"""
    
    def __init__(self, api_key: str, system_prompt: str | None = None):
        self.client = OpenAI(api_key=api_key)
        prompt = system_prompt or self._load_system_prompt()
        self.system_prompt = prompt.strip() if isinstance(prompt, str) else DEFAULT_SYSTEM_PROMPT
        
    def _load_system_prompt(self) -> str:
        """Загружает системный промпт для ИИ"""
        return DEFAULT_SYSTEM_PROMPT

    def generate_thread_content(self, topic: str = None) -> Dict:
        """
        Генерирует контент для карточек через OpenAI API
        
        Args:
            topic: Опциональная тема для генерации
            
        Returns:
            Dict с темой и репликами
        """
        user_message = "Сгенерируй новый вирусный пост в формате JSON."
        if topic:
            user_message += f" {topic}"
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.9,
                response_format={"type": "json_object"}
            )
            
            content = json.loads(response.choices[0].message.content)
            
            # Добавляем ID если отсутствует
            if "id" not in content:
                content["id"] = f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
                
            return content
            
        except Exception as e:
            raise Exception(f"Ошибка при генерации контента: {str(e)}")


class ImageGenerator:
    """Генератор изображений с наложением текста"""
    
    def __init__(self, width: int = 1080, height: int = 1080):
        self.width = width
        self.height = height
        self.colors = {
            'background': '#1a1a2e',
            'role': '#e94560',
            'text': '#ffffff',
            'accent': '#0f3460'
        }
        
    def _get_font(self, size: int, bold: bool = False):
        """Возвращает шрифт DejaVu Sans (поддерживает кириллицу и латиницу)"""
        font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            return ImageFont.load_default()

    def _format_sentences(self, text: str) -> str:
        """Убирает лишние пробелы перед знаками препинания и переносит предложения на новую строку"""
        text = re.sub(r'\s+([,.;!?])', r'\1', text)
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'([.!?])\s+(?=[^\s])', r'\1\n', text)
        return text.strip()
    
    def _parse_markdown(self, text: str) -> List[tuple]:
        """
        Простой парсер markdown для **жирного** и *курсива*
        Возвращает список кортежей (текст, стиль)
        """
        result = []
        i = 0
        current_text = ""
        
        while i < len(text):
            if i < len(text) - 1 and text[i:i+2] == '**':
                if current_text:
                    result.append((current_text, 'normal'))
                    current_text = ""
                # Ищем закрывающие **
                end = text.find('**', i + 2)
                if end != -1:
                    content = text[i+2:end]
                    # Удаляем пробелы перед знаками препинания
                    content = re.sub(r'\s+([,.;!?])', r'\1', content)
                    result.append((content, 'bold'))
                    i = end + 2
                else:
                    current_text += text[i]
                    i += 1
            elif text[i] == '*':
                if current_text:
                    result.append((current_text, 'normal'))
                    current_text = ""
                # Ищем закрывающий *
                end = text.find('*', i + 1)
                if end != -1:
                    content = text[i+1:end]
                    content = re.sub(r'\s+([,.;!?])', r'\1', content)
                    result.append((content, 'italic'))
                    i = end + 1
                else:
                    current_text += text[i]
                    i += 1
            else:
                current_text += text[i]
                i += 1
        
        if current_text:
            clean_text = re.sub(r'\s+([,.;!?])', r'\1', current_text)
            result.append((clean_text, 'normal'))
            
        return result if result else [(re.sub(r'\s+([,.;!?])', r'\1', text), 'normal')]
    
    def _should_keep_with_next(self, word: str) -> bool:
        """Проверяет, нужно ли держать слово вместе со следующим"""
        short_words = {'и', 'в', 'на', 'с', 'по', 'за', 'из', 'о', 'у', 'к', 'до', 'от', 'не'}
        return word.lower() in short_words or len(word) <= 2
    
    def _ends_with_punctuation(self, word: str) -> bool:
        """Проверяет, заканчивается ли слово знаком препинания"""
        return word and word[-1] in '.,!?;:—-'
    
    def _split_word_and_punctuation(self, word: str) -> tuple:
        """Отделяет знаки препинания от слова"""
        if not word:
            return '', ''
        
        punctuation = ''
        text = word
        
        # Собираем знаки препинания с конца
        while text and text[-1] in '.,!?;:—-':
            punctuation = text[-1] + punctuation
            text = text[:-1]
        
        return text, punctuation
    
    def create_card(self, role: str, text: str, card_number: int, total_cards: int) -> Image.Image:
        """Создает одну карточку с репликой"""
        img = Image.new('RGB', (self.width, self.height), self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Шрифты
        role_font = self._get_font(60, bold=True)
        text_font = self._get_font(45)
        text_font_bold = self._get_font(45, bold=True)
        counter_font = self._get_font(30)
        
        padding = 160
        y_position = padding
        
        # Рисуем роль
        role_bbox = draw.textbbox((0, 0), role, font=role_font)
        role_width = role_bbox[2] - role_bbox[0]
        role_x = (self.width - role_width) // 2
        
        draw.text((role_x, y_position), role, fill=self.colors['role'], font=role_font)
        y_position += (role_bbox[3] - role_bbox[1]) + 60
        
        # Разделитель
        line_margin = 200
        draw.line([(line_margin, y_position), (self.width - line_margin, y_position)], 
                  fill=self.colors['accent'], width=3)
        y_position += 120
        
        # Парсим и рисуем текст с форматированием
        text = self._format_sentences(text)
        parsed_text = self._parse_markdown(text)
        max_width = self.width - (padding * 2)
        
        # Собираем все сегменты в единый список слов с их стилями
        word_segments = []
        for segment, style in parsed_text:
            parts = segment.split('\n')
            for part_index, part in enumerate(parts):
                if part.strip():
                    words = part.split()
                    for word in words:
                        word_text, punctuation = self._split_word_and_punctuation(word)
                        if word_text:
                            word_segments.append((word_text, style, punctuation))
                        elif punctuation:
                            word_segments.append(('', style, punctuation))
                if part_index < len(parts) - 1:
                    word_segments.append((None, 'newline', ''))
        
        # Формируем строки с учетом правил
        lines = []
        current_line = []
        i = 0
        
        while i < len(word_segments):
            word_text, style, punctuation = word_segments[i]

            if style == 'newline':
                if current_line:
                    lines.append(current_line)
                    current_line = []
                i += 1
                continue
            
            # Проверяем, поместится ли слово в текущую строку
            full_word = word_text + punctuation
            test_line = current_line + [(full_word, style)]
            test_text = ' '.join([w for w, _ in test_line])
            
            test_font = text_font_bold if style == 'bold' else text_font
            bbox = draw.textbbox((0, 0), test_text, font=test_font)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line.append((full_word, style))
                i += 1
            else:
                if current_line:
                    last_word = current_line[-1][0]
                    
                    if self._should_keep_with_next(last_word.rstrip('.,!?;:—-')):
                        if len(current_line) > 1:
                            lines.append(current_line[:-1])
                            current_line = [current_line[-1], (full_word, style)]
                            i += 1
                        else:
                            lines.append(current_line)
                            current_line = [(full_word, style)]
                            i += 1
                    else:
                        lines.append(current_line)
                        current_line = [(full_word, style)]
                        i += 1
                else:
                    current_line = [(full_word, style)]
                    i += 1
        
        if current_line:
            lines.append(current_line)

        punctuation_regex = re.compile(r'\s+([,.;!?])')
        cleaned_lines = []
        for line in lines:
            cleaned_line = []
            for word, style in line:
                cleaned_word = punctuation_regex.sub(r'\1', word)
                cleaned_line.append((cleaned_word, style))
            cleaned_lines.append(cleaned_line)
        lines = cleaned_lines

        # Рисуем строки
        for line_segments in lines:
            line_text = ' '.join([word for word, _ in line_segments])
            bbox = draw.textbbox((0, 0), line_text, font=text_font)
            line_width = bbox[2] - bbox[0]
            x = (self.width - line_width) // 2
            for idx, (word, style) in enumerate(line_segments):
                current_font = text_font_bold if style == 'bold' else text_font
                draw.text((x, y_position), word, fill=self.colors['text'], font=current_font)
                word_bbox = draw.textbbox((0, 0), word, font=current_font)
                word_width = word_bbox[2] - word_bbox[0]
                x += word_width
                if idx < len(line_segments) - 1:
                    next_word = line_segments[idx + 1][0]
                    if not (style in ('bold', 'italic') and next_word in {'.', ',', '!', ':', ';'}):
                        space_bbox = draw.textbbox((0, 0), ' ', font=current_font)
                        x += space_bbox[2] - space_bbox[0]
            
            bbox = draw.textbbox((0, 0), 'Ay', font=text_font)
            y_position += (bbox[3] - bbox[1]) + 20
        
        # Счетчик карточек внизу
        counter_text = f"{card_number}/{total_cards}"
        counter_bbox = draw.textbbox((0, 0), counter_text, font=counter_font)
        counter_x = (self.width - (counter_bbox[2] - counter_bbox[0])) // 2
        counter_y = self.height - padding
        
        draw.text((counter_x, counter_y), counter_text, 
                  fill=self.colors['accent'], font=counter_font)
        
        return img


# ============================================       
# STREAMLIT-ПРИЛОЖЕНИЕ
# ============================================


def _init_session_vars() -> None:
    """Инициализирует переменные в session_state"""
    defaults = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "random_topics_history": [],
        "generated_batches": [],
        "is_generating": False,
        "batch_indices": {},
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            # Используем копию для изменяемых структур
            st.session_state[key] = value[:] if isinstance(value, list) else value


def _sanitize_filename(value: str) -> str:
    """Создает безопасное имя файла на основе темы"""
    safe_chars = "_- "
    cleaned = "".join(ch if ch.isalnum() or ch in safe_chars else "_" for ch in value)
    collapsed = "_".join(filter(None, cleaned.split()))
    return collapsed[:80] or "thread"


def _build_random_topic_request(history: List[str]) -> str:
    """Формирует текст запроса для случайной темы"""
    if not history:
        return "Любая тема, которая точно удивит"
    history_text = ", ".join(history)
    return f"Любая, кроме {history_text}"


def _images_to_zip(images: List[Dict], theme: str) -> io.BytesIO:
    """Упаковывает изображения одной генерации в ZIP"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, image_info in enumerate(images, start=1):
            filename = f"{_sanitize_filename(theme)}_{idx:02d}_{image_info['role']}.png"
            zip_file.writestr(filename, image_info["bytes"])
    zip_buffer.seek(0)
    return zip_buffer


def _shift_batch_index(batch_id: str, delta: int, total: int) -> None:
    """Смещает текущий индекс карточек для конкретной подборки"""
    indices = st.session_state["batch_indices"]
    current = indices.get(batch_id, 0)
    new_idx = max(0, min(total - 1, current + delta))
    indices[batch_id] = new_idx


def _render_image_viewer(batch_id: str, theme: str, images: List[Dict]) -> None:
    """Отображает изображения с переключением вперед/назад"""
    indices = st.session_state["batch_indices"]
    total = len(images)
    if total == 0:
        st.warning("Нет изображений для отображения.")
        return

    if batch_id not in indices or indices[batch_id] >= total:
        indices[batch_id] = 0

    current_idx = indices[batch_id]
    outer_left, center_col, outer_right = st.columns([1, 3, 1])

    with center_col:
        st.markdown(f"**Тема:** {theme}")
        button_col, image_col, button_col_right = st.columns([1, 8, 1], gap="small")

        with button_col:
            st.button(
                "◀",
                key=f"prev_{batch_id}",
                disabled=current_idx <= 0,
                use_container_width=True,
                on_click=_shift_batch_index,
                args=(batch_id, -1, total),
            )

        with button_col_right:
            st.button(
                "▶",
                key=f"next_{batch_id}",
                disabled=current_idx >= total - 1,
                use_container_width=True,
                on_click=_shift_batch_index,
                args=(batch_id, 1, total),
            )

    current_idx = indices[batch_id]
    current_image = images[current_idx]

    with image_col:
        caption = f"{current_idx + 1}/{total} · {current_image['role']}"
        display_width = max(1, current_image.get("width", 1080) // 2)
        st.image(current_image["bytes"], caption=caption, width=display_width)


def main() -> None:
    st.set_page_config(page_title="Threads Card Generator", layout="wide")
    _init_session_vars()

    st.title("Генератор карточек Threads")
    st.caption("Создавайте вирусные карточки в один клик и скачивайте целую подборку одним архивом.")
    with st.expander("Текущий системный промпт", expanded=False):
        st.text_area(
            "Промпт",
            st.session_state.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
            height=420,
            disabled=True,
        )

    # Сайдбар с настройками
    with st.sidebar:
        st.header("Настройки")
        api_key_input = st.text_input(
            "OpenAI API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
            help="Ключ будет использоваться только локально для генерации контента.",
        )
        if api_key_input != st.session_state.get("api_key"):
            st.session_state["api_key"] = api_key_input.strip()

        prompt_input = st.text_area(
            "Системный промпт",
            value=st.session_state.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
            height=420,
            help="Эта инструкция передается модели. Можно настроить под свои задачи.",
            key="prompt_editor",
        )
        apply_col, hint_col = st.columns([1, 1])
        with apply_col:
            apply_prompt = st.button("Применить промпт", type="secondary")
        with hint_col:
            st.caption("нажать 2 раза")

        if apply_prompt:
            st.session_state["system_prompt"] = prompt_input or DEFAULT_SYSTEM_PROMPT
            st.success("Промпт обновлен.")

        st.subheader("История случайных тем")
        history = st.session_state.get("random_topics_history", [])
        if history:
            st.markdown("\n".join(f"- {topic}" for topic in history))
        else:
            st.info("История пока пуста — сгенерируйте первую случайную тему.")

        if st.button("Очистить историю случайных тем", type="secondary"):
            st.session_state["random_topics_history"] = []
            st.success("История случайных тем очищена.")

    user_topic = st.text_input(
        "Тема поста",
        placeholder="Введите тему или оставьте поле пустым для случайной генерации",
    ).strip()

    generate_disabled = st.session_state["is_generating"]
    generate_button = st.button(
        "Сгенерировать карточки",
        type="primary",
        disabled=generate_disabled,
    )

    if generate_button and not st.session_state["is_generating"]:
        if not st.session_state["api_key"]:
            st.warning("Укажите OpenAI API Key в настройках, чтобы продолжить.")
        else:
            st.session_state["is_generating"] = True
            with st.spinner("Идет генерация контента и изображений..."):
                try:
                    topic_used = user_topic
                    used_random_topic = False

                    if not topic_used:
                        topic_used = _build_random_topic_request(st.session_state["random_topics_history"])
                        used_random_topic = True

                    content_generator = ThreadsCardGenerator(
                        api_key=st.session_state["api_key"],
                        system_prompt=st.session_state.get("system_prompt"),
                    )
                    thread_content = content_generator.generate_thread_content(topic_used)

                    replies = thread_content.get("replies", [])
                    if not replies:
                        raise ValueError("Модель вернула пустой список реплик. Попробуйте снова.")

                    image_generator = ImageGenerator()
                    total_cards = len(replies)
                    generated_images = []

                    for idx, reply in enumerate(replies, start=1):
                        role = reply.get("role", f"Реплика {idx}")
                        text = reply.get("text", "")
                        card_img = image_generator.create_card(role, text, idx, total_cards)
                        buffer = io.BytesIO()
                        card_img.save(buffer, format="PNG")
                        generated_images.append(
                            {
                                "role": role,
                                "text": text,
                                "bytes": buffer.getvalue(),
                                "width": card_img.width,
                                "height": card_img.height,
                            }
                        )

                    theme = thread_content.get("theme", topic_used)
                    batch_id = thread_content.get("id") or f"thread_{uuid.uuid4().hex[:8]}"
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    batch_payload = {
                        "id": batch_id,
                        "theme": theme,
                        "topic_used": topic_used,
                        "replies": replies,
                        "images": generated_images,
                        "cta": thread_content.get("cta"),
                        "tags": thread_content.get("tags", []),
                        "timestamp": timestamp,
                    }

                    st.session_state["generated_batches"] = [batch_payload]
                    st.session_state["batch_indices"] = {batch_id: 0}

                    if used_random_topic and theme not in st.session_state["random_topics_history"]:
                        st.session_state["random_topics_history"].append(theme)

                except Exception as error:
                    st.error(f"Не удалось завершить генерацию: {error}")
                finally:
                    st.session_state["is_generating"] = False

    if st.session_state["generated_batches"]:
        st.divider()
        st.subheader("Сгенерированные подборки")

        for batch in reversed(st.session_state["generated_batches"]):
            container = st.container()
            with container:
                meta_text = (
                    f"ID: `{batch['id']}` · Создано: {batch['timestamp']} · "
                    f"CTA: {batch.get('cta', 'не задано')}"
                )
                st.caption(meta_text)

                if batch.get("tags"):
                    st.caption("Теги: " + " ".join(batch["tags"]))

                _render_image_viewer(batch["id"], batch["theme"], batch["images"])

                zip_file = _images_to_zip(batch["images"], batch["theme"])
                download_label = f"Скачать ZIP для темы «{batch['theme']}»"
                st.download_button(
                    download_label,
                    data=zip_file,
                    file_name=f"{_sanitize_filename(batch['theme'])}.zip",
                    mime="application/zip",
                    key=f"download_{batch['id']}",
                )
                st.write("---")
    else:
        st.info("Здесь появятся карточки после первой генерации.")


if __name__ == "__main__":
    main()
