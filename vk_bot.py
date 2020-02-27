import json
import time
from datetime import datetime, timedelta
from random import randint
from threading import Thread
import traceback
import logging

import requests 
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType, VkLongPoll

from database import Database
from settings import api_url, vk_api_key
from yandex_geocoder import str_to_geo_data


event_types = []


def get_pages(lst, count):
    offset = 0
    pages = []
    while(offset < len(lst)):
        pages.append(lst[offset:offset+count])
        offset += count
    return pages


def pretty_date(date):
    if(type(date) == type(0)):
        date = datetime.fromtimestamp(date)
    months = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря"
    }
    return f'{str(100+date.hour)[1:]}:{str(100+date.minute)[1:]} {date.day} {months[date.month]}'


def gen_event_types():
    global event_types
    url = api_url + 'event_types'
    responce = requests.get(url)
    responce = responce.json()
    event_types = [ [i['type'], i['title'] ] for i in responce.values()]


def get_data_from_api(event_type, begin, city, end=None, street=None, house=None):
    if(end is None):
        end = begin + timedelta(days=1)
    ut_begin = int(time.mktime(begin.timetuple()))
    ut_end = int(time.mktime(end.timetuple()))

    output = []
    offset = 0
    count = 50
    while(True):
        url = api_url + f'event?type={event_type}&begin={ut_begin}&end={ut_end}&count={count}&offset={offset}&city={city}'
        if(street):
            url = url + '&street=' + street
        if(house):
            url = url + '&house=' + house
        respound = requests.get(url)
        data = respound.json()
        if(len(data)):
            output += list(data.values())
        offset += count
        if(len(data) < count):
            break
    return output


def type_to_label(inp_title):
    for i in event_types:
        if(i[0] == inp_title):
            return i[1]


def get_alert_messaages_on_days(user, date, inp_event_type=None, days=1):
    if(type(date) == type(0)):
        date = datetime.fromtimestamp(date)
    city = user['city']
    street = user.get('street')
    house = user.get('house')
    events = []
    was_event_types = []
    for wish in user['wish_list']:
        event_type = wish['event_type']
        if(inp_event_type != None and inp_event_type != event_type or event_type in was_event_types):
            continue
        was_event_types.append(event_type)
        begin = date - timedelta(days=0, hours=1)
        end = date + timedelta(days=days, hours=1)
        events += get_data_from_api(event_type, begin, city, end, street, house)

    messages = []
    for event in events:
        pretty_begin = pretty_date(event['begin'])
        pretty_end = pretty_date(event['end'])
        messages.append(f'{event["description"]} произойдет c {pretty_begin} до {pretty_end} по адресу {event["full_address"]}')
    return messages


def create_mailing(vk, user, messages):
    for message in messages:
        vk.method('messages.send', {
            'random_id': randint(0, 2**31),
            'user_id': user['user_id'],
            'message': message
        })


def processing_button(user, old_payload = None):
    '''
    Принемает на вход данные с нажатой кнопки.
    Возвращает dict с полями 
    > update_alert_time
    > update_wish_list
    > waiting_adress
    > keypad
    > message
    > del_wish
    > get_inf_on_days
    Чтобы прочесть этот моудуль, надо свернуть все и понять общую структуру
    '''
    if(old_payload == None):
        old_payload = '{"val": "return", "prnt": {"title": "main", "page": 0, "val": "", "prnt":{}}, "title": "sub", "page": 0}'
    else:
        old_payload = old_payload.replace("'", '"')

    old_payload = json.loads(old_payload)
    new_payload = {
        'title': old_payload['title'],
        'page': old_payload['page'],
        'prnt': old_payload.get('prnt')
    }
    output = {
        'message': ''
    }

    # Реагирование на кнопку, определение новой клавиатуры
    if  (old_payload['title'] == 'main'):
        if(old_payload['val'] == 'sub'):
            new_payload['title'] = 'sub'
            output['message'] = 'Список категорий.\nНажмите, чтобы посмотреть список событий по данной категории.'
        elif(old_payload['val'] == 'alert_time'):
            new_payload['title'] = 'alert_time'
            output['message'] = 'Выберете время, в которое будут приходить сообщения.'
        elif(old_payload['val'] == 'unsub'):
            new_payload['title'] = 'unsub'
            output['message'] = 'Список ваших подписок.\nНажмите, чтобы отписаться.'
        elif(old_payload['val'] == 'adr_change'):
            new_payload['title'] = 'adr_change'
            output['message'] = 'Напишите адрес, который хотите указать'
            output['waiting_adress'] = True
        elif(old_payload['val'] == 'show'):
            new_payload['title'] = 'show'
            output['message'] = 'Выберете день, за который хотите получить все события, по вашим подпискам'
        new_payload['page'] = 0
        new_payload['prnt'] = old_payload.copy()
    elif(old_payload['title'] == 'sub'):
        if(old_payload['val'] == 'next_page'):
            new_payload['page'] += 1
            output['message'] = 'Переход на следущую страницу.'
        elif(old_payload['val'] == 'previous_page'):
            new_payload['page'] -= 1
            output['message'] = 'Переход на предыдущую страницу.'
        elif(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            del new_payload['val']
            output['message'] = 'Главное меню.'
        else:
            new_payload['title'] = 'days'
            new_payload['page'] = 0
            new_payload['prnt'] = old_payload.copy()
            output['message'] = 'Выберете количество дней, за которое хотите получить оповещание.'
    elif(old_payload['title'] == 'days'):
        if(old_payload['val'] == 'next_page'):
            new_payload['page'] += 1
            output['message'] = 'Следующая страница.'
        elif(old_payload['val'] == 'previous_page'):
            new_payload['page'] -= 1
            output['message'] = 'Предыдущая страница'
        elif(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            del new_payload['val']
            output['message'] = 'Выбор события.'
        else:
            new_payload = old_payload.copy()
            del new_payload['val']

            event_type = new_payload['prnt']['val']
            event_time_before = old_payload['val']
            user['wish_list'].append({'event_type': event_type, 'event_time_before': event_time_before})
            output['update_wish_list'] = (event_type, event_time_before)
            output['message'] = 'Добавлена подписка на %s за %d дней до события' % (type_to_label(old_payload['prnt']['val']), event_time_before)
    elif(old_payload['title'] == 'unsub'):
        if(old_payload['val'] == 'next_page'):
            new_payload['page'] += 1
            output['message'] = 'Следующая страница.'
        elif(old_payload['val'] == 'previous_page'):
            new_payload['page'] -= 1
            output['message'] = 'Предыдущая страница.'
        elif(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            del new_payload['val']
            output['message'] = 'Главное меню.'
        else:
            new_payload['title'] = 'unsub_days'
            new_payload['page'] = 0
            new_payload['prnt'] = old_payload.copy()
            output['message'] = 'Выбирете от оповещания за какое количество дней хотите отписаться'
    elif(old_payload['title'] == 'unsub_days'):
        if(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            del new_payload['val']
            output['message'] = 'Список ваших подписок.\nНажмите, чтобы отписаться.'
        else:
            new_payload = old_payload.copy()
            del new_payload['val']

            event_type = new_payload['prnt']['val']
            event_time_before = old_payload['val']
            user['wish_list'].remove({'event_type': event_type, 'event_time_before': event_time_before})
            output['del_wish'] = (event_type, event_time_before)
            output['message'] = 'Удалена подписка на %s за %d дней до события' % (type_to_label(old_payload['prnt']['val']), event_time_before)
    elif(old_payload['title'] == 'alert_time'):
        if(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            output['message'] = 'Главное меню'
        else:
            output['update_alert_time'] = old_payload['val']
            user['alert_time'] = old_payload['val']
            output['message'] = 'Время опевещаний установлено на %d:00.' % old_payload['val']
    elif(old_payload['title'] == 'adr_change'):
        if(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            output['message'] = 'Главное меню.'
    elif(old_payload['title'] == 'show'):
        if(old_payload['val'] == 'return'):
            new_payload = old_payload['prnt']
            del new_payload['val']
            output['message'] = 'Главное меню'
        else:
            output['get_inf_on_days'] = old_payload['val']

    keyboard = VkKeyboard(one_time=False)

    #  Определение содержания основных кнопок
    if  (new_payload['title'] == 'main'):
        buttons = [
            ['sub', 'Меню подписок'],
            ['alert_time', 'Меню выбора времени оповещания'],
            ['unsub', 'Меню управления подписками'],
            ['adr_change', 'Меню смены адреса'],
            ['show', 'Все события за конкретный день']
        ]
    elif(new_payload['title'] == 'sub'):
        buttons = event_types
    elif(new_payload['title'] == 'days'):
        possible_days = {1, 2, 7, 30}
        event_type = new_payload['prnt']['val']
        selected_days = set(
            map(
                lambda a: a['event_time_before'],
                filter(
                    lambda b: b['event_type'] == event_type,
                    user['wish_list']
                )
            )
        )
        buttons = list(possible_days - selected_days)
        buttons = [[button, f"За {button} {'день' if button == 1 else ('дня' if 2 <= button <= 4 else 'дней')} до события"] for button in buttons]
    elif(new_payload['title'] == 'unsub'): 
        buttons = []
        for wish in user['wish_list']:
            button = [
                wish['event_type'],
                type_to_label(wish['event_type'])
            ]
            if(button not in buttons):
                buttons.append(button)
        if(len(buttons) == 0):
            output['message'] = 'На данный момент подписок нет. Чтобы это исправить зайдите в Меню подписок'
    elif(new_payload['title'] == 'unsub_days'):
        wishs = filter(
            lambda wish: wish['event_type'] == new_payload['prnt']['val'], 
            user['wish_list']
        )
        buttons = list(map(
            lambda wish: wish['event_time_before'],
            wishs
        ))
        buttons = [[button, f"За {button} {'день' if button%10 == 1 else ('дня' if 2 <= button%10 <= 4 else 'деней')} до события"] for button in buttons]
    elif(new_payload['title'] == 'alert_time'):
        buttons = [[i * 4 + j for j in range(4)] for i in range(6)]
    elif(new_payload['title'] == 'adr_change'):
        buttons = []
    elif(new_payload['title'] == 'show'):
        buttons = [
            ['1', 'Сегодня'],
            ['2', 'Завтра'],
            ['3', 'Послезавтра'],
            ['1-7', 'На ближайшую неделю'],
            ['1-30', 'На ближайший месяц']            
        ]

    # Если нужны странички
    left_arrow = False
    right_arrow = False
    if(len(buttons) > 9):
        pages_list = get_pages(buttons, 8)
        page = new_payload['page']
        if(page > 0):
            left_arrow = True
        if(page < len(pages_list) - 1):
            right_arrow = True
        buttons = pages_list[page]

    # Создание основных кнопок
    if(new_payload['title'] == 'alert_time'):
        for line in buttons:
            for button in line:
                button_payload = new_payload.copy()
                button_payload.update({'val': button})
                button_payload = '{\"button\": \"%s\"}' % str(button_payload)
                if(user['alert_time'] == button):
                    color = VkKeyboardColor.POSITIVE
                else:
                    color = VkKeyboardColor.DEFAULT
                keyboard.add_button(label=f"{button}:00", payload=button_payload, color=color)
            keyboard.add_line()
    elif(len(buttons) and type(buttons[0]) == type([])):
        for val, label in buttons:
            button_payload = new_payload.copy()
            button_payload.update({'val': val})
            button_payload = '{\"button\": \"%s\"}' % str(button_payload)
            keyboard.add_button(label=label, payload=button_payload)
            if not(new_payload['title'] == 'main' and [val, label] == buttons[-1]):
                keyboard.add_line()
    elif(len(buttons)):
        for button in buttons:
            button_payload = new_payload.copy()
            button_payload.update({'val': button})
            button_payload = '{\"button\": \"%s\"}' % str(button_payload)
            keyboard.add_button(label=button, payload=button_payload)
            keyboard.add_line()

    # Создание стрелок
    if(left_arrow):
        arrow_payload = new_payload.copy()
        arrow_payload['val'] = 'previous_page'
        arrow_payload = '{\"button\": \"%s\"}' % str(arrow_payload)
        keyboard.add_button(label= '←', payload=arrow_payload)
    if(right_arrow):
        arrow_payload = new_payload.copy()
        arrow_payload['val'] = 'next_page'
        arrow_payload = '{\"button\": \"%s\"}' % str(arrow_payload)
        keyboard.add_button(label= '→', payload=arrow_payload)
    if(left_arrow or right_arrow):
        keyboard.add_line()

    # Создние кнопки Назад
    if(new_payload['title'] != 'main'):
        return_payload = new_payload.copy()
        return_payload.update({'val': 'return'})
        return_payload = '{\"button\": \"%s\"}' % str(return_payload)
        keyboard.add_button(label='Назад', payload=return_payload)

    output['keyboard'] = keyboard.get_keyboard()

    return output


def processing_message(vk, db, event):
    user = db.find_by_user_id(event.user_id)
    if(user is None):
        db.insert_one({'user_id': event.user_id})
        user = db.find_by_user_id(event.user_id)

    text = event.text
    logging.info("%s %d %s" % (datetime.now(), user['user_id'], text))
    payload = {}
    if(event.extra_values.get('payload') is not None):
        payload = json.loads(event.extra_values['payload'])
    answer = {'random_id': randint(0, 2**31), 'user_id': event.user_id, 'message': 'Описание потеряно'}
    do_answer = True

    if(text.lower() == 'debug restart'):
        db.users.remove({'user_id': user['user_id']})
        answer['message'] = 'Акаунт сброшен'
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(label='Начать')
        answer['keyboard'] = keyboard.get_keyboard()

    # Нажал кнопку "Начать"
    elif(text.lower() in ['начать', 'start'] and user['chat_stage'] == 'address_waiting'):
        message = """Добро пожаловать в Gradinformer
        Я могу сообщить тебе о том, что происходит в твоем городе.
        Например, об отключении воды в твоем доме или мероприятии недалеко от тебя.
        
        Для регистрации напиши место проживания.
        Минимально необходимая информация - город проживания"""
        message = message.replace(' '*8, '')
        answer['message'] =  message

    # Ввел адрес
    elif(user['chat_stage'] == 'address_waiting' and not payload.get('button')):
        geodata = str_to_geo_data(text)
        if(len(geodata)):
            for key in geodata[0]:
                db.update(user, key, geodata[0][key])
            db.update(user, 'chat_stage', 'menu')

            answer.update(processing_button(user))
            message = f"""Установлен адрес {geodata[0]['full_address']}.
            Изменить или уточнить его можно в Меню смены адреса."""
            message = message.replace(' '*12, '')
            answer['message'] = message
        else:
            answer['message'] = 'Адрес не опознан, попробуйте еще раз'
    
    #Нажал на кнопку
    elif(payload.get('button') != None):
        try:
            menu_output = processing_button(user, payload['button'])
            if(menu_output.get('keyboard')):
                answer['keyboard'] = menu_output['keyboard']
            if(menu_output.get('message')):
                answer['message'] = menu_output['message']
            if(menu_output.get('update_alert_time')):
                db.update(user, 'alert_time', menu_output['update_alert_time'])
            if(menu_output.get('update_wish_list')):
                db.add_in_wish_list(user, *menu_output['update_wish_list'])
            if(menu_output.get('waiting_adress')):
                if(user['chat_stage'] == 'menu'):
                    db.update(user, 'chat_stage', 'address_waiting')
                else:
                    db.update(user, 'chat_stage', 'menu')
            if(menu_output.get('del_wish')): 
                db.del_from_wish_list(user, *menu_output['del_wish'])
            if(menu_output.get('get_inf_on_days')):
                if(menu_output['get_inf_on_days'].count('-')):
                    first, second = map(int, menu_output['get_inf_on_days'].split('-'))
                    date = datetime.now() - timedelta(days=first-1)
                    days = second - first
                    messages = get_alert_messaages_on_days(user, date=date, days=days)
                else:
                    date = datetime.now() - timedelta(days=int(menu_output['get_inf_on_days']) - 1)
                    messages = get_alert_messaages_on_days(user, date=date)

                if(len(messages)):
                    create_mailing(vk, user, messages)
                    do_answer = False
                else:
                    answer['message'] = 'Событий не найдено'
        except Exception as err:
            logging.error(err.__traceback__)
            answer['message'] = 'Что-то пошло не так. Попробуйте еще раз или повторите поптытку позже'

    else:
        answer['message'] = 'Команда не определена'
    if(do_answer):
        try:
            vk.method('messages.send', answer)
        except:
            logging.info('%s %d %s' % (datetime.now(), user['user_id'], 'Не удалось отправить сообщение'))



def answer_bot(vk, db):
    while(True):
        try:
            longpoll = VkLongPoll(vk)
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    Thread(target=processing_message, args=(vk, db, event,)).start()
        except:
            pass

def alert_bot(vk, db):
    previous_hour = datetime.now().hour - 1
    while(True):
        if(datetime.now().hour != previous_hour):
            previous_hour = datetime.now().hour

            cursor = db.get_cursor_by_alert_time(datetime.now().hour)
            for user in cursor:
                messages = []
                for wish in user['wish_list']:
                    date = datetime.now() + timedelta(days=wish['event_time_before'] - 1)
                    messages += get_alert_messaages_on_days(user, date, wish['event_type'])
                Thread(target=create_mailing, args=(vk, user, messages)).start()

        time.sleep(120)


if __name__ == "__main__":
    vk = vk_api.VkApi(token=vk_api_key)
    db = Database()

    gen_event_types()

    answer_bot_thread = Thread(target=answer_bot, args=(vk, db,))
    alert_bot_tread   = Thread(target=alert_bot,  args=(vk, db,))

    answer_bot_thread.start()
    alert_bot_tread.start()
