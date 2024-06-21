from flask import Flask, request, jsonify, send_from_directory, url_for, session
from transformers import pipeline
from gtts import gTTS
import os
import time
from flask_session import Session

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Зареждане на многоезичния NLP модел, поддържащ български език
qa_pipeline = pipeline("question-answering", model="deepset/xlm-roberta-base-squad2")

# Примерни данни за продукти с цени
products = {
    "тениски": {"sizes": ["S", "M", "L", "XL"], "colors": ["червен", "син", "зелен", "черен"], "availability": True, "price": 20},
    "дънки": {"sizes": ["M", "L", "XL"], "colors": ["черен", "син"], "availability": False, "price": 40},
    "рокли": {"sizes": ["S", "M", "L", "XL"], "colors": ["червен", "син", "черен", "зелен"], "availability": True, "price": 35},
    "якета": {"sizes": ["M", "L", "XL", "XXL"], "colors": ["черен", "син", "зелен", "червен"], "availability": True, "price": 50},
    "обувки": {"sizes": ["38", "39", "40", "41", "42", "43"], "colors": ["бял", "черен", "син"], "availability": True, "price": 60},
    "шапки": {"sizes": ["S", "M", "L"], "colors": ["червен", "черен", "зелен"], "availability": True, "price": 15},
    "ръкавици": {"sizes": ["S", "M", "L"], "colors": ["черен", "син"], "availability": True, "price": 10},
    "очила": {"sizes": ["универсален"], "colors": ["черен", "син", "зелен"], "availability": True, "price": 25},
    "чанти": {"sizes": ["малка", "средна", "голяма"], "colors": ["червен", "черен", "син"], "availability": True, "price": 30},
    "колани": {"sizes": ["S", "M", "L", "XL"], "colors": ["черен", "кафяв"], "availability": True, "price": 18},
    "часовници": {"sizes": ["малък", "среден", "голям"], "colors": ["черен", "сребрист", "златен"], "availability": True, "price": 100},
    "анцуг": {"sizes": ["S", "M", "L", "XL"], "colors": ["черен", "син", "сив"], "availability": True, "price": 45},
    "ризи": {"sizes": ["S", "M", "L", "XL", "XXL"], "colors": ["бял", "син", "черен"], "availability": True, "price": 25},
    "панталони": {"sizes": ["S", "M", "L", "XL"], "colors": ["черен", "сив", "син"], "availability": True, "price": 35},
    "чорапи": {"sizes": ["35-38", "39-42", "43-46"], "colors": ["бял", "черен", "сив"], "availability": True, "price": 5},
}

# Често задавани въпроси и отговори
faq = {
    "какви методи за плащане приемате": "Приемаме плащания с кредитни карти, дебитни карти и PayPal.",
    "какъв е срокът за доставка": "Срокът за доставка е от 3 до 5 работни дни.",
    "каква е политиката ви за връщане": "Можете да върнете продукт в рамките на 30 дни от датата на покупката.",
    "как мога да проследя поръчката си": "Можете да проследите поръчката си чрез нашия уебсайт, използвайки номера на поръчката.",
    "какви са разходите за доставка": "Разходите за доставка зависят от адреса на доставка и теглото на поръчката.",
    "как да използвам промоционален код": "Можете да въведете промоционалния код в полето за отстъпка по време на плащане.",
    "имате ли опция за наложен платеж": "Да, предлагаме опция за наложен платеж.",
    "как да анулирам поръчката си": "Можете да анулирате поръчката си чрез вашия профил на нашия уебсайт.",
    "какви цветове са налични за даден продукт": "Наличните цветове зависят от продукта, но обикновено предлагаме червен, син, зелен и черен.",
    "имате ли този продукт на склад": "Да, продуктът е наличен на склад.",
    "как да създам профил на вашия сайт": "Можете да създадете профил, като кликнете на 'Регистрация' на нашия уебсайт и следвате инструкциите.",
    "мога ли да променя адреса за доставка след като съм направил поръчка": "Можете да промените адреса за доставка, ако поръчката все още не е изпратена.",
    "имате ли физически магазин": "Не, ние сме изцяло онлайн магазин.",
    "как да се свържа с клиентската поддръжка": "Можете да се свържете с нашата клиентска поддръжка чрез нашия уебсайт или на телефон 123-456-789.",
    "имате ли програма за лоялност": "Да, имаме програма за лоялност, където можете да събирате точки и да ги обменяте за отстъпки.",
}

# Създаване на папка за поръчки
if not os.path.exists('ПОРЪЧКИ'):
    os.makedirs('ПОРЪЧКИ')

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    query = req.get('queryText', '').lower()
    is_voice = req.get('isVoice', False)

    print(f"Получен въпрос: {query}")

    answer = ""
    end_chat = False

    # Проверка за израз на благодарност 
    if "благодаря" in query:
        end_chat = True
        session.pop('order', None)  # Изчистване на сесията при отговор "Благодаря"
    else:
        # Отговори на често задавани въпроси
        if any(greeting in query for greeting in ["здравей", "здравейте", "добър ден", "добро утро", "добър вечер"]):
            answer = "Здравейте! Как мога да ви помогна днес?"
        elif "как си" in query or "как сте" in query:
            answer = "Добре съм, благодаря! Как мога да ви помогна днес?"

        else:
            # Обработка на често задавани въпроси
            for question, response in faq.items():
                if question in query:
                    answer = response
                    break

            # Проверка за въпроси, свързани с конкретни продукти
            if not answer:
                for product, details in products.items():
                    if product in query:
                        if "цветове" in query:
                            answer = f"Наличните цветове за {product} са {', '.join(details['colors'])}."
                        elif "цена" in query:
                            answer = f"Цената на {product} е {details['price']} лева."
                        elif "размери" in query:
                            answer = f"Наличните размери за {product} са {', '.join(details['sizes'])}."
                        elif "наличност" in query:
                            availability = "наличен" if details["availability"] else "не е наличен"
                            answer = f"{product.capitalize()} в момента е {availability}."
                        break

            # Ако няма отговор от FAQ или за продукт, продължаваме с обработка на поръчка
            if not answer:
                if "искам да поръчам" in query:
                    session['order'] = {'stage': 'product'}
                    answer = "Какво бихте искали да поръчате?"
                elif 'order' in session:
                    order = session['order']
                    stage = order.get('stage')

                    if stage == 'product':
                        for product in products.keys():
                            if product in query:
                                session['order']['product'] = product
                                session['order']['stage'] = 'color'
                                answer = f"Избрахте {product}. Какъв цвят желаете?"
                                break
                    elif stage == 'color':
                        product = session['order']['product']
                        details = products[product]
                        for color in details['colors']:
                            if color in query:
                                session['order']['color'] = color
                                session['order']['stage'] = 'confirm'
                                answer = (f"Избрахте цвят {color}. "
                                          f"Вашата поръчка: един брой. {product} "
                                          f"цвят {color}. Обща цена: {details['price']} лева. "
                                          "Благодаря за поръчката! Моля, потвърдете с 'Потвърждавам'.")
                                break
                    elif stage == 'confirm':
                        if "потвърждавам" in query:
                            session['order']['stage'] = 'name'
                            answer = "Моля, предоставете вашите две имена."
                    elif stage == 'name':
                        session['order']['name'] = query
                        session['order']['stage'] = 'phone'
                        answer = "Моля, предоставете вашия телефонен номер."
                    elif stage == 'phone':
                        session['order']['phone'] = query
                        session['order']['stage'] = 'address'
                        answer = "Моля, предоставете адреса за доставка."
                    elif stage == 'address':
                        session['order']['address'] = query
                        order_details = session['order']
                        answer = (f"Благодаря за поръчката, {order_details['name']}! "
                                  f"Ще се свържем с вас на {order_details['phone']} за потвърждение на доставката до {order_details['address']}.")
                        
                        # Записване на поръчката във файл
                        order_id = int(time.time())
                        order_file_path = os.path.join('ПОРЪЧКИ', f"order_{order_id}.txt")
                        with open(order_file_path, 'w', encoding='utf-8') as file:
                            file.write(f"Поръчка №{order_id}\n")
                            file.write(f"Продукт: {order_details['product']}\n")
                            file.write(f"Цвят: {order_details['color']}\n")
                            file.write(f"Име: {order_details['name']}\n")
                            file.write(f"Телефон: {order_details['phone']}\n")
                            file.write(f"Адрес: {order_details['address']}\n")
                            file.write(f"Цена: {products[order_details['product']]['price']} лв\n")
                        
                        session['order'] = {'stage': 'complete'}

                else:
                    answer = "Не мога да отговоря на този въпрос. Моля, задайте въпрос свързан с нашия онлайн магазин."

    # Ако до този момент няма зададен отговор, връщаме съобщението по подразбиране
    if not answer and not end_chat:
        answer = "Не мога да отговоря на този въпрос. Моля, задайте въпрос свързан с нашия онлайн магазин."

    print(f"Изпратен отговор: {answer}")

    response_data = {'fulfillmentText': answer, 'endChat': end_chat}
    
    if is_voice and answer:
        try:
            timestamp = int(time.time())
            audio_file_path = os.path.join("static", f"response_{timestamp}.mp3")
            tts = gTTS(answer, lang='bg')
            tts.save(audio_file_path)
            audio_url = url_for('static', filename=f"response_{timestamp}.mp3")
            response_data['audioUrl'] = audio_url
            print(f"Аудио отговорът е създаден успешно: {audio_url}")
        except Exception as e:
            print(f"Грешка при създаването на аудио отговор: {e}")

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
