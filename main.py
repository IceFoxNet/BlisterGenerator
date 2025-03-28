from pip._internal import main as pip

while True:
    try:
        from PIL import Image, ImageFont, ImageDraw
        from rembg import remove
        import os, cv2, time, aiohttp
        import numpy as np, pathlib, yadisk, gspread
    except ImportError as e:
        package = e.msg.split()[-1][1:-1]
        pip(['install', package])
    else:
        break

# ======================= ФУНКЦИИ =======================

# Функция для переноса текста по ширине
def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if font.getbbox(test_line)[2] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

# Асинхронная функция загрузки изображений
async def download_image(session, art):
    global downloaded_image_buffer
    try:
        url = f"https://img.bricklink.com/ItemImage/MN/0/{art}.png"
        response = await session.get(url)
        if response.status == 200:
            with open(downloaded_image_buffer, "wb") as f:
                f.write(await response.read())
            return downloaded_image_buffer
        elif response.status == 404:
            url = f"https://img.bricklink.com/ItemImage/SN/0/{art}.png"
            response = await session.get(url)
            if response.status == 200:
                with open(downloaded_image_buffer, "wb") as f:
                    f.write(await response.read())
                return downloaded_image_buffer
            else:
                print(f"Ошибка загрузки изображения для артикула {art}. Статус: {response.status}")
                return None
    except Exception as e:
        print(f"Ошибка при загрузке изображения для артикула {art}: {e}")
        return None

# Функция проверки фона изображения
def is_white_background(image_path, threshold=240):
                """
                Проверяет, является ли фон изображения белым.
                threshold — пороговое значение яркости для определения белого цвета.
                """
                try:
                    with Image.open(image_path) as img:
                        img = img.convert("RGBA")
                        # Берем верхнюю часть изображения для анализа фона
                        width, height = img.size
                        top_pixels = [img.getpixel((x, 0)) for x in range(width)]
                        # Проверяем, насколько пиксели близки к белому цвету
                        white_pixels = [pixel for pixel in top_pixels if all(val >= threshold for val in pixel[:3])]
                        # Если большинство пикселей белые, считаем фон белым
                        return len(white_pixels) / len(top_pixels) > 0.8
                except Exception as e:
                    print(f"Ошибка при проверке фона изображения: {e}")
                    return False

# ======================= НАСТРОЙКА =======================

workspace = pathlib.Path(__file__).parent.resolve()
downloaded_image_buffer = os.path.join(workspace, 'download_buffer.png')

SE = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))

# Загрузка шрифтов
try:
    font_path_regular = os.path.join(workspace, "Inter.ttf")
    font_path_medium = os.path.join(workspace, "Inter-Medium.ttf")
    font_path_bold = os.path.join(workspace, "Inter-Bold.ttf")

    main_font_29 = ImageFont.truetype(font_path_regular, 29)
    main_font_12 = ImageFont.truetype(font_path_regular, 12)
    main_font_42_medium = ImageFont.truetype(font_path_medium, 42)
    main_font_82_bold = ImageFont.truetype(font_path_bold, 82)
    main_font_49_bold = ImageFont.truetype(font_path_bold, 49)

except IOError:
    print("Шрифты 'Inter.ttf', 'Inter-Medium.ttf' или 'Inter-Bold.ttf' не найдены. Проверьте пути.")

try:
    with Image.open(os.path.join(workspace, "sample.jpg")) as background_template:
        background_template.load()
except FileNotFoundError:
    print("Файл 'sample.jpg' не найден.")

# ======================= ОБРАБОТКА ИЗОБРАЖЕНИЙ =======================

# Асинхронная основная обработка изображений
async def main(start: int, end: int, setup: dict):

    if start < 3: start = 3
    
    sheet: gspread.spreadsheet.Spreadsheet = setup.get('GoogleSheet')
    yandex: yadisk.YaDisk = setup.get('YandexDisk')
    worksheet = sheet.worksheet("📦 Фигурки")
    arts = worksheet.col_values(4)[2:]  # Все данные из столбца 4 (артикул)
    
    async with aiohttp.ClientSession(proxy='http://user258866:pe9qf7@166.0.211.142:7576') as session:
        for i in range(start-2, end-1):
            if i < len(arts):
                art = arts[i]
            else:
                break  # Завершаем цикл, если индекс выходит за пределы
            if not art:
                print(f"Пропущена строка {i+1}: значение отсутствует.")
                continue

            typ = 'Minifigure'
            price = (worksheet.cell(i+3, 7).value or "Не указана") + '₽'
            name = worksheet.cell(i+3, 3).value or "Без названия"
            series = worksheet.cell(i+3, 2).value or "Без серии"

            # Загрузка изображения
            file_path = await download_image(session, art)
            if not file_path:
                continue

            # Работа с фоном и наложением изображений
            main_template = background_template.copy().convert("RGBA")
            overlay = Image.new(mode="RGBA", size=main_template.size, color=(0, 0, 0, 0))

            # Добавление рамок Frame_Gray.png и Frame_Green.png
            try:
                frame_gray_path = os.path.join(workspace, "Frame_Gray.png")
                frame_green_path = os.path.join(workspace, "Frame_Green.png")

                if os.path.exists(frame_gray_path):
                    with Image.open(frame_gray_path).convert("RGBA") as frame_gray:
                        gray_position = (60, 560)
                        overlay.paste(frame_gray, gray_position, mask=frame_gray)

                if os.path.exists(frame_green_path):
                    with Image.open(frame_green_path).convert("RGBA") as frame_green:
                        frame_bg = Image.new(mode="RGBA", size=frame_green.size, color=(255, 255, 255, 255))
                        frame_green_with_bg = Image.alpha_composite(frame_bg, frame_green)
                        green_position = (60, 894)
                        overlay.paste(frame_green_with_bg, green_position)
            except FileNotFoundError as e:
                print(f"Ошибка при добавлении рамок: {e}")
                continue

            # Наложение логотипа серии
            series_file = os.path.join(workspace, f'series/{series.replace(" ", "")}.png')
            if os.path.exists(series_file):
                try:
                    with Image.open(series_file) as img3:
                        overlay.paste(img3.resize((960, 167)), (60, 60))
                except FileNotFoundError:
                    print(f"Файл {series_file} не найден.")
                    continue

            # Добавляем текст на изображение
            drawer = ImageDraw.Draw(overlay)

            # Добавляем текст с подчеркиванием
            art_position = (102, 745)
            drawer.text(art_position, art, font=main_font_49_bold, fill='black')

            text_bbox = drawer.textbbox((0, 0), art, font=main_font_49_bold)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            underline_y = art_position[1] + text_height + 16
            line_width = 5

            drawer.line(
                [(art_position[0], underline_y), (art_position[0] + text_width, underline_y)],
                fill='black', width=line_width
            )

            # Многострочный текст для длинных названий
            lines = wrap_text(name, main_font_29, 400)
            y_offset = 0
            for line in lines:
                drawer.text((102, 589 + y_offset), line, font=main_font_29, fill='black')
                y_offset += 40

            # Текст "typ"
            drawer.text((102, 931.5), typ, font=main_font_42_medium, fill='black')

            # Текст с ценой
            drawer.text((60, 393), price, font=main_font_82_bold, fill='black')

            # Функция для разбивки текста на строки
            def wrap_text_to_box(text, font, max_width):
                words = text.split(' ')
                lines = []
                current_line = ""

                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    line_width = drawer.textbbox((0, 0), test_line, font=font)[2] - \
                                 drawer.textbbox((0, 0), test_line, font=font)[0]

                    if line_width <= max_width:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word

                if current_line:
                    lines.append(current_line)

                return lines

            # Параметры
            start_x = 60
            start_y = 1020
            box_width = 960  # Максимальная ширина блока
            box_height = 60  # Высота блока для текста
            line_height = 16  # Высота строки (интервал между строками)

            # Текст с товарным знаком
            trademark_text = (
                "LEGO, the LEGO logo, the Minifigure, DUPLO, the DUPLO logo, NINJAGO, "
                "the NINJAGO logo, the FRIENDS logo, the HIDDEN SIDE logo, the MINIFIGURES logo, "
                "MINDSTORMS and the MINDSTORMS logo are trademarks of the LEGO Group. ©2023 The LEGO Group. "
                "All rights reserved."
            )

            # Разбиваем текст на строки, учитывая максимальную ширину
            lines = wrap_text_to_box(trademark_text, main_font_12, box_width)

            # Общая высота текста
            total_text_height = len(lines) * line_height

            # Вычисляем смещение по вертикали для выравнивания по центру
            y_offset = start_y + (box_height - total_text_height) // 2

            # Рисуем каждую строку текста с выравниванием по ширине и высоте
            for line in lines:
                # Вычисляем ширину текущей строки
                line_width = drawer.textbbox((0, 0), line, font=main_font_12)[2] - \
                             drawer.textbbox((0, 0), line, font=main_font_12)[0]

                # Вычисляем смещение по горизонтали для выравнивания по центру
                x_offset = start_x + (box_width - line_width) // 2

                # Рисуем строку текста
                drawer.text((x_offset, y_offset), line, font=main_font_12, fill="#808080")

                # Увеличиваем Y для следующей строки
                y_offset += line_height
            
            # =========================== ПЕРВАЯ ФОТОГРАФИЯ (ФИГУРКА) ===========================
            
            img1 = main_template.copy()
            
            # Проверяем, является ли фон белым
            if not is_white_background(file_path):
                try:
                    img = Image.open(file_path)
                    result = remove(img)
                    # img = cv2.imread(file_path)
                    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    # _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
                    # contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    # largest_contour = max(contours, key=cv2.contourArea)
                    # object_mask = np.zeros_like(mask)
                    # cv2.drawContours(object_mask, [largest_contour], -1, 255, thickness=cv2.FILLED)
                    # SE = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
                    # object_mask = cv2.bitwise_not(cv2.morphologyEx(cv2.bitwise_not(object_mask), cv2.MORPH_DILATE, SE))
                    # object_mask = cv2.GaussianBlur(object_mask, (1, 1), 0)
                    # result = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                    # result[:, :, 3] = object_mask
                    output_path = file_path.replace('.jpg', '_no_bg.png')
                    result.save(output_path)
                except Exception as e:
                    print(f"Ошибка при удалении фона для изображения {art} (вторая фотография): {e}")
                    output_path = file_path  # Оставляем оригинал, если что-то пошло не так
            else:
                output_path = file_path  # Если фон белый, оставляем оригинальное изображение
            
            # Открываем изображение для первой фотографии
            try:
                with Image.open(output_path).convert("RGBA") as img2:
                    img2 = img2.resize((int(624 / img2.height * img2.width), 624))
                    white_bg = Image.new("RGBA", img2.size, (255, 255, 255, 255))
                    img2 = Image.alpha_composite(white_bg, img2)

                    center_x = (520 + 1080) / 2
                    position_x = center_x - img2.width / 2
                    position_y = 1020 - img2.height

                    img1.paste(img2, (int(position_x), int(position_y)))
            except FileNotFoundError:
                print(f"Изображение {output_path} не найдено.")
                continue

            # Сохраняем первое финальное изображение
            img1 = Image.alpha_composite(img1, overlay)
            final_output_path = os.path.join(workspace, f'{art}_1.png')
            img1.save(final_output_path)
            try:
                yandex.makedirs(f'Авито/{art}')
            except:
                pass
            yandex.upload(final_output_path, f'Авито/{art}/{art}_1.png', overwrite=True)
            print(f"Первая фотография для артикула {art} сохранена: {final_output_path}")
            os.remove(final_output_path)
            
            # =========================== ВТОРАЯ ФОТОГРАФИЯ (ФИГУРКА + КОРОБКА) ===========================
            
            second_output_path = os.path.join(workspace, f'{art}_2.png')
            res_img2 = main_template.copy()
            
            # Основной блок обработки
            try:
                img = Image.open(file_path)
                result = remove(img)
                # img = cv2.imread(file_path)
                # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
                # contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                # largest_contour = max(contours, key=cv2.contourArea)
                # object_mask = np.zeros_like(mask)
                # cv2.drawContours(object_mask, [largest_contour], -1, 255, thickness=cv2.FILLED)
                # SE = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
                # object_mask = cv2.bitwise_not(cv2.morphologyEx(cv2.bitwise_not(object_mask), cv2.MORPH_DILATE, SE))
                # object_mask = cv2.GaussianBlur(object_mask, (1, 1), 0)
                # result = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                # result[:, :, 3] = object_mask
                output_path = file_path.replace('.jpg', '_no_bg.png')
                result.save(output_path)
            except Exception as e:
                print(f"Ошибка при удалении фона для изображения {art}: {e}")
                continue
            
            try:
                # Очищаем название серии от пробелов и других символов
                cleaned_series = series.replace(" ", "").replace("/", "_").replace("\\", "_").replace(":", "_").replace(
                    "*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")

                # Формируем путь к файлу в папке Blister
                blister_image_path = os.path.join(os.path.join(workspace, "Blister"),                         
                f"{cleaned_series}_Front.png")  # Или .jpg, в зависимости от формата
                if os.path.exists(blister_image_path):
                    with Image.open(blister_image_path).convert("RGBA") as blister_img:
                        # Накладываем изображение из Blister по тем же координатам, что и фигурка
                        blister_img = blister_img.resize((int(730 / blister_img.height * blister_img.width), 730))
                        center_x = (500 + 1080) / 2
                        position_x = center_x - blister_img.width / 2
                        position_y = 1025 - blister_img.height
                        res_img2.paste(blister_img, (int(position_x), int(position_y)), mask=blister_img)
                else:
                    print(f"Изображение Blister для серии {series} не найдено: {blister_image_path}")
                    continue

                # Загружаем и накладываем фотографию фигурки
                with Image.open(output_path).convert("RGBA") as img2:
                    img2 = img2.resize((int(245 / img2.height * img2.width), 245))

                    # Создаем изображение с прозрачностью 75%
                    img2_with_opacity = Image.new("RGBA", img2.size)
                    for x in range(img2.width):
                        for y in range(img2.height):
                            r, g, b, a = img2.getpixel((x, y))
                            img2_with_opacity.putpixel((x, y),
                                                       (r, g, b, int(a * 0.75)))  # Устанавливаем прозрачность 75%

                    center_x = (510 + 1080) / 2
                    position_x = center_x - img2_with_opacity.width / 2
                    position_y = 925 - img2_with_opacity.height

                    res_img2.paste(img2_with_opacity, (int(position_x), int(position_y)), mask=img2_with_opacity)
            except FileNotFoundError:
                print(f"Изображение {output_path} не найдено.")
                continue

            # Сохраняем финальное изображение (вторая фотография)
            res_img2 = Image.alpha_composite(res_img2, overlay)
            res_img2.save(second_output_path)
            yandex.upload(second_output_path, f'Авито/{art}/{art}_2.png', overwrite=True)
            print(f"Вторая фотография для артикула {art} сохранена: {second_output_path}")
            os.remove(second_output_path)

            # =========================== ТРЕТЬЯ ФОТОГРАФИЯ (КОРОБКА) ===========================

            third_output_path = os.path.join(workspace, f'{art}_3.png')
            img3 = main_template.copy()

            # Формируем путь к файлу в папке Blister
            blister_image_path = os.path.join(os.path.join(workspace, "Blister"),
            f"{cleaned_series}_Back.png")  # Или .jpg, в зависимости от формата
            if os.path.exists(blister_image_path):
                with Image.open(blister_image_path).convert("RGBA") as blister_img:
                    # Накладываем изображение из Blister по тем же координатам, что и фигурка
                    blister_img = blister_img.resize((int(730 / blister_img.height * blister_img.width), 730))
                    center_x = (500 + 1080) / 2
                    position_x = center_x - blister_img.width / 2
                    position_y = 1025 - blister_img.height
                    img3.paste(blister_img, (int(position_x), int(position_y)), mask=blister_img)
            else:
                print(f"Изображение Blister для серии {series} не найдено: {blister_image_path}")
                continue
            
            img3 = Image.alpha_composite(img3, overlay)
            img3.save(third_output_path)
            yandex.upload(third_output_path, f'Авито/{art}/{art}_3.png', overwrite=True)
            print(f"Третья фотография для артикула {art} сохранена: {third_output_path}")
            os.remove(third_output_path)
            
            # Добавляем задержку между запросами
            time.sleep(3)  # Задержка на 1 секунду между запросами
