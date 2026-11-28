import asyncio
import json
import random
import re
from typing import Dict, Any, List, Union, Optional, AsyncGenerator, Tuple
from bs4 import BeautifulSoup


class SlideProcessor:
    def __init__(self):
        self.img_pool: List[Dict] = []
        self.transition_index: int = 0
        self.transition_template: Union[Dict, None] = None

    def _generate_nanoid(self, length: int = 10) -> str:
        import uuid
        return str(uuid.uuid4())[:length]

    def _check_text_type(self, el: Dict, text_type: str) -> bool:
        return (el.get('type') == 'text' and el.get('textType') == text_type) or \
            (el.get('type') == 'shape' and el.get('text') and el['text'].get(
                'textType') == text_type)

    def _get_useable_templates(self, templates: List[Dict], n: int, text_type: str) -> List[Dict]:
        if n == 1:
            list_templates = [
                slide for slide in templates
                if not any(self._check_text_type(el, text_type) for el in slide.get('elements', [])) and
                   len([el for el in slide.get('elements', []) if self._check_text_type(el, 'title')]) == 1 and
                   len([el for el in slide.get('elements', []) if self._check_text_type(el, 'content')]) == 1
            ]
            if list_templates:
                return list_templates

        target: Union[Dict, None] = None

        list_templates = [
            slide for slide in templates
            if len([el for el in slide.get('elements', []) if self._check_text_type(el, text_type)]) >= n
        ]

        if not list_templates:
            sorted_templates = sorted(templates, key=lambda slide: len([
                el for el in slide.get('elements', []) if self._check_text_type(el, text_type)
            ]))
            target = sorted_templates[-1] if sorted_templates else None
        else:
            target = min(list_templates, key=lambda slide: abs(
                len([el for el in slide.get('elements', []) if self._check_text_type(el, text_type)]) - n
            ))

        if not target:
            return []

        target_len = len([el for el in target.get('elements', []) if self._check_text_type(el, text_type)])
        return [slide for slide in templates if
                len([el for el in slide.get('elements', []) if self._check_text_type(el, text_type)]) == target_len]

    def _get_font_info(self, content: str) -> Dict:
        match_font_size = re.search(r'font-size:\s*(\d+)px', content, re.IGNORECASE)
        font_size = int(match_font_size.group(1)) if match_font_size else 16

        match_font_family = re.search(r'font-family:\s*([^;"]+)', content, re.IGNORECASE)
        font_family = match_font_family.group(1).strip() if match_font_family else 'Arial'

        return {'fontSize': font_size, 'fontFamily': font_family}

    def _get_adapted_fontsize(self, text: str, font_size: int, font_family: str, width: int, max_line: int) -> int:
        if len(text) * font_size / 2 > width * max_line:
            return max(10, int(font_size * 0.8))
        return font_size

    def _get_new_text_element(self, el: Dict, text: str, max_line: int, longest_text: str = None,
                              digit_padding: bool = False) -> Dict:

        is_type_text = el.get('type') == 'text'
        content_key = 'content' if is_type_text else 'text'

        original_html_content = el.get(content_key) if is_type_text else el.get('text', {}).get('content')

        if not isinstance(original_html_content, str):
            original_html_content = ""

        new_element = el.copy()
        if not is_type_text:
            new_element['text'] = new_element.get('text', {}).copy()

        is_html = '<' in original_html_content and '>' in original_html_content

        if is_html:
            soup = BeautifulSoup(original_html_content, 'html.parser')
            target_tag = None
            for tag_name in ['span', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                found_tag = soup.find(tag_name)
                if found_tag and found_tag.get_text(strip=True):
                    target_tag = found_tag
                    break

            if not target_tag:
                target_tag = soup.find(True)

            original_plain_text = ""
            if target_tag:
                original_plain_text = target_tag.get_text()

                if digit_padding:
                    if text.isdigit():
                        target_tag.string = text.zfill(2)
                    else:
                        target_tag.string = text
                else:
                    target_tag.string = text
            else:
                if digit_padding and text.isdigit():
                    original_html_content = original_html_content.replace(original_plain_text, text.zfill(2))
                else:
                    original_html_content = original_html_content.replace(original_plain_text, text)

                soup = BeautifulSoup(original_html_content, 'html.parser')
                target_tag = soup.find(True)

            font_info = self._get_font_info(original_html_content)

            size = self._get_adapted_fontsize(
                text=longest_text or text,
                font_size=font_info['fontSize'],
                font_family=font_info['fontFamily'],
                width=el.get('width', 100) - 20,
                max_line=max_line,
            )

            if target_tag and target_tag.has_attr('style'):
                current_style = target_tag['style']
                if 'font-size' in current_style.lower():
                    updated_style = re.sub(r'font-size:\s*\d+px', f'font-size: {size}px', current_style,
                                           flags=re.IGNORECASE)
                else:
                    updated_style = f"{current_style}; font-size: {size}px;"
                target_tag['style'] = updated_style.strip(';')
            elif target_tag:
                target_tag['style'] = f"font-size: {size}px;"

            if is_type_text:
                new_element['content'] = str(soup)
            else:
                new_element['text']['content'] = str(soup)

        else:
            if digit_padding and text.isdigit():
                final_text_content = text.zfill(2)
            else:
                final_text_content = text

            padding = 10
            width = el.get('width', 100) - padding * 2 - 10
            default_font_size = 16
            default_font_family = 'Arial'

            size = self._get_adapted_fontsize(
                text=longest_text or text,
                font_size=default_font_size,
                font_family=default_font_family,
                width=width,
                max_line=max_line,
            )

            if is_type_text:
                new_element['content'] = final_text_content
            else:
                new_element['text']['content'] = final_text_content
                new_element['text']['fontSize'] = size

        if size < 15:
            new_element['lineHeight'] = 1.2

        return new_element

    def _get_useable_image(self, el: Dict) -> Union[Dict, None]:
        img: Union[Dict, None] = None
        imgs: List[Dict] = []

        if el.get('width') == el.get('height'):
            imgs = [img for img in self.img_pool if img.get('width') == img.get('height')]
        elif el.get('width') > el.get('height'):
            imgs = [img for img in self.img_pool if img.get('width') > img.get('height')]
        else:
            imgs = [img for img in self.img_pool if img.get('width') <= img.get('height')]

        if not imgs:
            imgs = self.img_pool

        if imgs:
            img = random.choice(imgs)
            self.img_pool = [item for item in self.img_pool if item.get('id') != img.get('id')]

        return img

    def _get_new_img_element(self, el: Dict) -> Dict:
        img = self._get_useable_image(el)
        if not img:
            return el

        scale = 1
        w = el.get('width', 0)
        h = el.get('height', 0)
        image_clip_data_range: List[List[float]] = [[0, 0], [0, 0]]
        radio = w / h if h != 0 else 0

        if img.get('width', 0) / img.get('height', 1) >= radio:
            scale = img.get('height', 1) / h if h != 0 else 1
            w = img.get('width', 0) / scale
            diff = (w - el.get('width', 0)) / 2 / w * 100 if w != 0 else 0
            image_clip_data_range = [[diff, 0], [100 - diff, 100]]
        else:
            scale = img.get('width', 0) / w if w != 0 else 1
            h = img.get('height', 0) / scale
            diff = (h - el.get('height', 0)) / 2 / h * 100 if h != 0 else 0
            image_clip_data_range = [[0, diff], [100, 100 - diff]]

        clip_shape = el.get('clip', {}).get('shape', 'rect') if el.get('clip') else 'rect'
        clip = {'range': image_clip_data_range, 'shape': clip_shape}
        src = img.get('src')

        return {**el, 'src': src, 'clip': clip}

    def get_md_content(self, content: str) -> str:
        regex = r'```markdown(.*?)```'
        match = re.search(regex, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content.replace('```markdown', '').replace('```', '')

    def get_json_content(self, content: str) -> str:
        regex = r'```json(.*?)```'
        match = re.search(regex, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content.replace('```json', '').replace('```', '')

    def load_template_slides(self, file_path, is_template=False):
        with open(file_path, "r", encoding="utf-8") as f:
            template_data = json.load(f)

        if is_template:
            if "slides" not in template_data:
                raise KeyError("Missing 'slides' key in template file")

            return template_data["slides"]

        return template_data

    def _validate_slide_data(self, slide_data: Dict[str, Any]) -> bool:
        return (isinstance(slide_data, dict) and
                "type" in slide_data and
                "data" in slide_data and
                isinstance(slide_data["data"], dict))

    def _create_error_slide(self, message: str) -> Dict[str, Any]:
        return {
            "type": "error",
            "data": {"message": message, "errorType": "slide_generation_error"}
        }

    async def _process_buffer_for_slides(self, current_buffer: str) -> AsyncGenerator[
        Tuple[Optional[Dict[str, Any]], str], None]:
        start_tag = "<slide>"
        end_tag = "</slide>"
        temp_buffer = current_buffer

        while True:
            start_index = temp_buffer.find(start_tag)
            if start_index == -1:
                break

            end_index = temp_buffer.find(end_tag, start_index + len(start_tag))
            if end_index == -1:
                break

            slide_json_str = temp_buffer[start_index + len(start_tag):end_index].strip()
            processed_length = end_index + len(end_tag)
            temp_buffer = temp_buffer[processed_length:]

            try:
                slide_data = json.loads(slide_json_str)

                if isinstance(slide_data, list):
                    if len(slide_data) > 0:
                        print(f"Warning: LLM returned array inside <slide> tag. Taking first element.")
                        slide_data = slide_data[0]
                    else:
                        raise ValueError("Empty array received inside <slide> tag.")

                if self._validate_slide_data(slide_data):
                    yield slide_data, current_buffer[
                                      current_buffer.find(slide_json_str) + len(slide_json_str) + len(end_tag):].strip()
                    await asyncio.sleep(0.5)

                    current_buffer = current_buffer[processed_length:].strip()
                else:
                    print(f"Malformed slide JSON (validation failed): {slide_json_str}")
                    yield self._create_error_slide(f"Malformed slide JSON: {slide_json_str}"), current_buffer[
                                                                                               processed_length:].strip()
                    await asyncio.sleep(0.5)
                    current_buffer = current_buffer[processed_length:].strip()

            except json.JSONDecodeError as e:
                print(f"JSON Decode Error for slide: {e} - Data: {slide_json_str}")
                break
            except ValueError as e:
                print(f"Value Error processing slide data: {e} - Data: {slide_json_str}")
                yield self._create_error_slide(f"Malformed slide structure: {str(e)}"), current_buffer[
                                                                                        processed_length:].strip()
                await asyncio.sleep(0.01)
                current_buffer = current_buffer[processed_length:].strip()
        yield None, temp_buffer

    async def _map_ai_slide_to_template(self, ai_slide_data: Dict[str, Any], template_slides: List[Dict]) -> Optional[
        Dict[str, Any]]:
        slide_type = ai_slide_data.get('type')
        data = ai_slide_data.get('data', {})

        if slide_type == 'cover':
            cover_templates = [slide for slide in template_slides if slide.get('type') == 'cover']
            if not cover_templates:
                return None
            chosen_template = random.choice(cover_templates)

            elements = []
            for el in chosen_template.get('elements', []):
                if el.get('type') == 'image' and el.get('imageType') and self.img_pool:
                    elements.append(self._get_new_img_element(el))
                elif el.get('type') in ('text', 'shape'):
                    if self._check_text_type(el, 'title') and data.get('title'):
                        elements.append(self._get_new_text_element(el, text=data['title'], max_line=1))
                    elif self._check_text_type(el, 'content') and data.get('text'):
                        elements.append(self._get_new_text_element(el, text=data['text'], max_line=3))
                    else:
                        elements.append(el)
                else:
                    elements.append(el)

            return {
                **chosen_template,
                'id': self._generate_nanoid(),
                'elements': elements,
            }

        elif slide_type == 'contents':
            items = data.get('items', [])
            processed_ai_slides_data = []
            if len(items) == 7:
                items1 = items[0:5]
                items2 = items[5:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 5})
            elif 7 < len(items) <= 12:
                items1 = items[0:6]
                items2 = items[6:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 6})
            elif len(items) == 13:
                items1 = items[0:6]
                items2 = items[6:11]
                items3 = items[11:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 6})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items3}, 'offset': 11})
            elif len(items) > 13:
                items1 = items[0:6]
                items2 = items[6:12]
                items3 = items[12:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 6})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items3}, 'offset': 12})
            else:
                processed_ai_slides_data.append(ai_slide_data)

            _contents_templates = self._get_useable_templates(
                [slide for slide in template_slides if slide.get('type') == 'contents'],
                len(items), 'item'
            )
            if not _contents_templates:
                return None
            chosen_template = random.choice(_contents_templates)

            sorted_item_ids = sorted(
                [el for el in chosen_template.get('elements', []) if self._check_text_type(el, 'item')],
                key=lambda el: el.get('left', 0) + el.get('top', 0) * 2
            )
            sorted_item_ids = [el['id'] for el in sorted_item_ids]

            sorted_number_item_ids = sorted(
                [el for el in chosen_template.get('elements', []) if self._check_text_type(el, 'itemNumber')],
                key=lambda el: el.get('left', 0) + el.get('top', 0) * 2
            )
            sorted_number_item_ids = [el['id'] for el in sorted_number_item_ids]

            longest_text_content_val = max(items, key=len, default='') if items else ''

            elements = []
            for el in chosen_template.get('elements', []):
                if el.get('type') == 'image' and el.get('imageType') and self.img_pool:
                    elements.append(self._get_new_img_element(el))
                elif el.get('type') in ('text', 'shape'):
                    if self._check_text_type(el, 'item'):
                        try:
                            index = sorted_item_ids.index(el['id'])
                            item_title = items[index]
                            if item_title:
                                elements.append(self._get_new_text_element(el, text=item_title, max_line=1,
                                                                           longest_text=longest_text_content_val))
                            else:
                                elements.append(el)
                        except (IndexError, ValueError):
                            elements.append(el)
                    elif self._check_text_type(el, 'itemNumber'):
                        try:
                            index = sorted_number_item_ids.index(el['id'])
                            offset = ai_slide_data.get('offset', 0)
                            elements.append(self._get_new_text_element(el, text=str(index + offset + 1), max_line=1,
                                                                       digit_padding=True))
                        except (IndexError, ValueError):
                            elements.append(el)
                    else:
                        elements.append(el)
                else:
                    elements.append(el)

            return {
                **chosen_template,
                'id': self._generate_nanoid(),
                'elements': elements,
            }

        elif slide_type == 'transition':
            transition_templates = [slide for slide in template_slides if slide.get('type') == 'transition']
            if not transition_templates:
                return None

            if not self.transition_template:
                self.transition_template = random.choice(transition_templates)

            self.transition_index += 1
            elements = []
            for el in self.transition_template.get('elements', []):
                if el.get('type') == 'image' and el.get('imageType') and self.img_pool:
                    elements.append(self._get_new_img_element(el))
                elif el.get('type') in ('text', 'shape'):
                    if self._check_text_type(el, 'title') and data.get('title'):
                        elements.append(self._get_new_text_element(el, text=data['title'], max_line=1))
                    elif self._check_text_type(el, 'content') and data.get('text'):
                        elements.append(self._get_new_text_element(el, text=data['text'], max_line=3))
                    elif self._check_text_type(el, 'partNumber'):
                        elements.append(self._get_new_text_element(el, text=str(self.transition_index), max_line=1,
                                                                   digit_padding=True))
                    else:
                        elements.append(el)
                else:
                    elements.append(el)

            return {
                **self.transition_template,
                'id': self._generate_nanoid(),
                'elements': elements,
            }

        elif slide_type == 'content':
            items = data.get('items', [])
            processed_ai_slides_data = []
            if len(items) == 5 or len(items) == 6:
                items1 = items[0:3]
                items2 = items[3:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 3})
            elif len(items) == 7 or len(items) == 8:
                items1 = items[0:4]
                items2 = items[4:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 4})
            elif len(items) == 9 or len(items) == 10:
                items1 = items[0:3]
                items2 = items[3:6]
                items3 = items[6:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 3})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items3}, 'offset': 6})
            elif len(items) > 10:
                items1 = items[0:4]
                items2 = items[4:8]
                items3 = items[8:]
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items1}})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items2}, 'offset': 4})
                processed_ai_slides_data.append({**ai_slide_data, 'data': {**data, 'items': items3}, 'offset': 8})
            else:
                processed_ai_slides_data.append(ai_slide_data)

            _content_templates = self._get_useable_templates(
                [slide for slide in template_slides if slide.get('type') == 'content'],
                len(items), 'item'
            )
            if not _content_templates:
                return None
            chosen_template = random.choice(_content_templates)

            sorted_title_item_ids = sorted(
                [el for el in chosen_template.get('elements', []) if self._check_text_type(el, 'itemTitle')],
                key=lambda el: el.get('left', 0) + el.get('top', 0) * 2
            )
            sorted_title_item_ids = [el['id'] for el in sorted_title_item_ids]

            sorted_text_item_ids = sorted(
                [el for el in chosen_template.get('elements', []) if self._check_text_type(el, 'item')],
                key=lambda el: el.get('left', 0) + el.get('top', 0) * 2
            )
            sorted_text_item_ids = [el['id'] for el in sorted_text_item_ids]

            sorted_number_item_ids = sorted(
                [el for el in chosen_template.get('elements', []) if self._check_text_type(el, 'itemNumber')],
                key=lambda el: el.get('left', 0) + el.get('top', 0) * 2
            )
            sorted_number_item_ids = [el['id'] for el in sorted_number_item_ids]

            item_titles_list = [i.get('title', '') for i in items if i.get('title')]
            item_texts_list = [i.get('text', '') for i in items if i.get('text')]

            longest_title_content_val = max(item_titles_list, key=len, default='') if item_titles_list else ''
            longest_text_content_val = max(item_texts_list, key=len, default='') if item_texts_list else ''

            elements = []
            for el in chosen_template.get('elements', []):
                if el.get('type') == 'image' and el.get('imageType') and self.img_pool:
                    elements.append(self._get_new_img_element(el))
                elif el.get('type') in ('text', 'shape'):
                    if len(items) == 1:
                        content_item = items[0]
                        if self._check_text_type(el, 'content') and content_item.get('text'):
                            elements.append(self._get_new_text_element(el, text=content_item['text'], max_line=6))
                        else:
                            elements.append(el)
                    else:
                        if self._check_text_type(el, 'itemTitle'):
                            try:
                                index = sorted_title_item_ids.index(el['id'])
                                content_item = items[index]
                                if content_item and content_item.get('title'):
                                    elements.append(self._get_new_text_element(el, text=content_item['title'],
                                                                               longest_text=longest_title_content_val,
                                                                               max_line=1))
                                else:
                                    elements.append(el)
                            except (IndexError, ValueError):
                                elements.append(el)
                        elif self._check_text_type(el, 'item'):
                            try:
                                index = sorted_text_item_ids.index(el['id'])
                                content_item = items[index]
                                if content_item and content_item.get('text'):
                                    elements.append(self._get_new_text_element(el, text=content_item['text'],
                                                                               longest_text=longest_text_content_val,
                                                                               max_line=4))
                                else:
                                    elements.append(el)
                            except (IndexError, ValueError):
                                elements.append(el)
                        elif self._check_text_type(el, 'itemNumber'):
                            try:
                                index = sorted_number_item_ids.index(el['id'])
                                offset = ai_slide_data.get('offset', 0)
                                elements.append(self._get_new_text_element(el, text=str(index + offset + 1), max_line=1,
                                                                           digit_padding=True))
                            except (IndexError, ValueError):
                                elements.append(el)
                        elif self._check_text_type(el, 'title') and data.get('title'):
                            elements.append(self._get_new_text_element(el, text=data['title'], max_line=1))
                        else:
                            elements.append(el)
                else:
                    elements.append(el)

            return {
                **chosen_template,
                'id': self._generate_nanoid(),
                'elements': elements,
            }

        elif slide_type == 'end':
            end_templates = [slide for slide in template_slides if slide.get('type') == 'end']
            if not end_templates:
                return None
            chosen_template = random.choice(end_templates)

            elements = []
            for el in chosen_template.get('elements', []):
                if el.get('type') == 'image' and el.get('imageType') and self.img_pool:
                    elements.append(self._get_new_img_element(el))
                elif el.get('type') in ('text', 'shape'):
                    if self._check_text_type(el, 'title') and data.get('title'):
                        elements.append(self._get_new_text_element(el, text=data['title'], max_line=1))
                    elif self._check_text_type(el, 'content') and data.get('text'):
                        elements.append(self._get_new_text_element(el, text=data['text'], max_line=3))
                    else:
                        elements.append(el)
                else:
                    elements.append(el)

            return {
                **chosen_template,
                'id': self._generate_nanoid(),
                'elements': elements,
            }

        return None
