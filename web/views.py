from django.shortcuts import redirect, render


def home(request):
    number = request.GET.get('number', '')
    if number.isascii() and number.isdigit() and int(number) > 0:
        return redirect(f'/table/{int(number)}/')
    return render(request, 'web/home.html')


def table_page(request, number):
    return render(request, 'web/table.html', {'number': number})


def orders_page(request, number):
    return render(request, 'web/orders.html', {'number': number})


def bill_page(request, number):
    return render(request, 'web/bill.html', {'number': number})


def staff_login(request):
    return render(request, 'web/staff_login.html')


def panel_page(request, section='home'):
    return render(request, 'web/panel.html', {'section': section})


def kitchen_page(request):
    return render(request, 'web/kitchen.html')


def waiter_page(request):
    return render(request, 'web/waiter.html')


def cashier_page(request):
    return render(request, 'web/cashier.html')


def gate_page(request):
    return render(request, 'web/gate.html')