"""

views.py – All views for the Expense Manager.

"""



import csv

import json

import io

import os

import datetime

from decimal import Decimal



from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth import login, logout, authenticate

from django.contrib.auth.decorators import login_required

from django.contrib.auth.forms import AuthenticationForm

from django.contrib import messages

from django.http import HttpResponse, JsonResponse

from django.db.models import Sum, Count, Q

import calendar

from django.db.models.functions import TruncMonth



from .models import Expense, CATEGORY_CHOICES

from .forms import RegisterForm, ExpenseForm, ReceiptUploadForm, ExpenseFilterForm

from .ocr import process_receipt

from .agents import get_expense_agent

from django.views.decorators.csrf import csrf_exempt

from django.conf import settings

from groq import Groq

from langchain_core.messages import HumanMessage





# ─── Auth ──────────────────────────────────────────────────────────────────────



def register_view(request):

    if request.user.is_authenticated:

        return redirect('dashboard')

    form = RegisterForm(request.POST or None)

    if form.is_valid():

        user = form.save()

        login(request, user)

        messages.success(request, f'Welcome, {user.first_name or user.username}! 🎉')

        return redirect('dashboard')

    return render(request, 'auth/register.html', {'form': form})





def login_view(request):

    if request.user.is_authenticated:

        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)

    if form.is_valid():

        user = form.get_user()

        login(request, user)

        messages.success(request, f'Welcome back, {user.first_name or user.username}!')

        return redirect(request.GET.get('next', 'dashboard'))

    return render(request, 'auth/login.html', {'form': form})





def logout_view(request):

    logout(request)

    return redirect('login')





# ─── Dashboard ─────────────────────────────────────────────────────────────────



@login_required

def dashboard(request):

    # Month filter from GET param (?month=YYYY-MM or 'overall')

    selected_month = request.GET.get('month', 'overall')

    expenses = Expense.objects.filter(user=request.user)



    if selected_month != 'overall':

        try:

            year, month = map(int, selected_month.split('-'))

            month_start = datetime.date(year, month, 1)

            # Fix: Get actual last day of month

            last_day = calendar.monthrange(year, month)[1]

            month_end = datetime.date(year, month, last_day)

            expenses = expenses.filter(date__range=[month_start, month_end])

            period_display = month_start.strftime('%B %Y')

            print(f"DEBUG: Filtered {expenses.count()} expenses for {selected_month} ({month_start} to {month_end})")

        except (ValueError, TypeError):

            selected_month = 'overall'

    else:

        period_display = 'All time'



    # Summary stats (filtered)

    total_spent = expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    count_total = expenses.count()



    # Recent 5 (filtered)

    recent = expenses.order_by('-date', '-created_at')[:5]



    # Category breakdown (filtered)

    cat_data = (

        expenses

        .values('category')

        .annotate(total=Sum('amount'), count=Count('id'))

        .order_by('-total')

    )

    cat_labels = [dict(CATEGORY_CHOICES).get(c['category'], c['category']) for c in cat_data]

    cat_amounts = [float(c['total']) for c in cat_data]



    # Monthly/Daily trend

    if selected_month != 'overall':

        # Single month: daily breakdown

        daily = (

            expenses

            .annotate(day=TruncMonth('date'))

            .values('day')

            .annotate(total=Sum('amount'))

            .order_by('day')

        )

        month_labels = [d['day'].strftime('%d %b') for d in daily]

        month_amounts = [float(d['total']) for d in daily]

    else:

        # All time: last 12 months trend

        twelve_months_ago = datetime.date.today() - datetime.timedelta(days=365)

        monthly = (

            expenses

            .filter(date__gte=twelve_months_ago)

            .annotate(month=TruncMonth('date'))

            .values('month')

            .annotate(total=Sum('amount'))

            .order_by('month')

        )

        month_labels = [m['month'].strftime('%b %Y') for m in monthly]

        month_amounts = [float(m['total']) for m in monthly]



# Available months for dropdown (last 24 months with data)

    two_years_ago = datetime.date.today() - datetime.timedelta(days=730)

    months_list_qs = (

        Expense.objects

        .filter(user=request.user, date__gte=two_years_ago)

        .annotate(month=TruncMonth('date'))

        .values('month')

        .distinct()

        .order_by('-month')

    )

    months_list = [

        {'value': m['month'].strftime('%Y-%m'), 'label': m['month'].strftime('%B %Y')}

        for m in months_list_qs

    ]



    context = {

        'total_spent':    total_spent,

        'count_total':    count_total,

        'recent':         recent,

        'period_display': period_display,

        'selected_month': selected_month,

        'months_list':    months_list,

        'cat_labels':     json.dumps(cat_labels),

        'cat_amounts':    json.dumps(cat_amounts),

        'month_labels':   json.dumps(month_labels),

        'month_amounts':  json.dumps(month_amounts),

    }

    return render(request, 'dashboard.html', context)





# ─── Expense CRUD ──────────────────────────────────────────────────────────────



@login_required

def expense_list(request):

    expenses = Expense.objects.filter(user=request.user)

    form = ExpenseFilterForm(request.GET or None)



    if form.is_valid():

        if form.cleaned_data.get('search'):

            q = form.cleaned_data['search']

            expenses = expenses.filter(

                Q(title__icontains=q) | Q(merchant__icontains=q) | Q(notes__icontains=q)

            )

        if form.cleaned_data.get('category'):

            expenses = expenses.filter(category=form.cleaned_data['category'])

        if form.cleaned_data.get('date_from'):

            expenses = expenses.filter(date__gte=form.cleaned_data['date_from'])

        if form.cleaned_data.get('date_to'):

            expenses = expenses.filter(date__lte=form.cleaned_data['date_to'])

        if form.cleaned_data.get('amount_min') is not None:

            expenses = expenses.filter(amount__gte=form.cleaned_data['amount_min'])

        if form.cleaned_data.get('amount_max') is not None:

            expenses = expenses.filter(amount__lte=form.cleaned_data['amount_max'])



    total = expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return render(request, 'expenses/list.html', {

        'expenses': expenses,

        'form': form,

        'total': total,

    })





@login_required

def expense_add(request):

    form = ExpenseForm(request.POST or None, request.FILES or None)

    if form.is_valid():

        expense = form.save(commit=False)

        expense.user = request.user

        expense.save()

        messages.success(request, 'Expense added!')

        return redirect('expense_list')

    return render(request, 'expenses/form.html', {'form': form, 'action': 'Add'})





@login_required

def expense_edit(request, pk):

    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    form = ExpenseForm(request.POST or None, request.FILES or None, instance=expense)

    if form.is_valid():

        form.save()

        messages.success(request, 'Expense updated!')

        return redirect('expense_list')

    return render(request, 'expenses/form.html', {'form': form, 'action': 'Edit', 'expense': expense})





@login_required

def expense_delete(request, pk):

    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':

        expense.delete()

        messages.success(request, 'Expense deleted.')

        return redirect('expense_list')

    return render(request, 'expenses/confirm_delete.html', {'expense': expense})





# ─── Receipt / OCR ────────────────────────────────────────────────────────────



@login_required

def upload_receipt(request):

    form = ReceiptUploadForm(request.POST or None, request.FILES or None)

    ocr_result = None



    if form.is_valid():

        uploaded_file = request.FILES['file']

        # Save temporarily

        from django.core.files.storage import default_storage

        path = default_storage.save(f'receipts/tmp_{uploaded_file.name}', uploaded_file)

        full_path = os.path.join(default_storage.location, path)



        ocr_result = process_receipt(full_path)

        ocr_result['file_url'] = default_storage.url(path)

        ocr_result['file_path'] = path



        # Pre-fill expense form with OCR data

        initial = {

            'title':    ocr_result.get('merchant', '') or 'Receipt',

            'amount':   ocr_result.get('total', ''),

            'date':     ocr_result.get('date', datetime.date.today()),

            'merchant': ocr_result.get('merchant', ''),

            'category': ocr_result.get('category', 'others'),

        }

        expense_form = ExpenseForm(initial=initial)

        return render(request, 'expenses/upload.html', {

            'form': form,

            'ocr': ocr_result,

            'expense_form': expense_form,

        })



    return render(request, 'expenses/upload.html', {'form': form})





@login_required

def save_scanned_expense(request):

    """Save an expense that was populated via OCR scan."""

    if request.method == 'POST':

        form = ExpenseForm(request.POST, request.FILES)

        if form.is_valid():

            expense = form.save(commit=False)

            expense.user = request.user

            expense.ocr_text = request.POST.get('ocr_text', '')



            # If no new image uploaded but we have the path from the scan step, reuse it

            if not expense.receipt_file:

                file_path = request.POST.get('receipt_file_path', '')

                if file_path:

                    expense.receipt_file = file_path



            expense.save()

            messages.success(request, 'Scanned expense saved! 🎉')

            return redirect('expense_list')



        # Invalid form — rebuild OCR context if possible

        return render(request, 'expenses/upload.html', {

            'form': ReceiptUploadForm(),

            'expense_form': form,

        })

    return redirect('upload_receipt')





# ─── Multi-Agent AI System ─────────────────────────────────────────────────────



@login_required

@csrf_exempt

def ai_agent(request):

    """Refactored Multi-agent AI endpoint using LangGraph and Groq"""

    if request.method != 'POST':

        return JsonResponse({'error': 'Method not allowed'}, status=405)



    try:

        data = json.loads(request.body)

        user_message = data.get('message', '').strip()

        

        if not user_message:

            return JsonResponse({'error': 'Empty message'}, status=400)



        # 1. Initialize the Graph

        # Note: In production, cache this 'app' object, don't recompile every request

        app = get_expense_agent(settings.GROQ_API_KEY)



        # 2. Run the Agentic Loop

        # We pass the user_id into the state so tools can access it

        inputs = {

            "messages": [HumanMessage(content=user_message)],

            "user_id": request.user.id

        }

        

        config = {"configurable": {"thread_id": str(request.user.id)}} # For persistent memory

        

        # Invoke the graph

        final_state = app.invoke(inputs, config=config)

        

        # 3. Extract the final response

        ai_response = final_state['messages'][-1].content



        return JsonResponse({

            'success': True,

            'response': ai_response,

            'history_length': len(final_state['messages'])

        })



    except Exception as e:

        import traceback

        print(f"[CRITICAL] Agent Error: {traceback.format_exc()}")

        return JsonResponse({

            'success': False,

            'response': "I'm having trouble accessing the database right now. Please try again."

        }, status=500)



# ─── Reports ──────────────────────────────────────────────────────────────────



@login_required

def download_csv(request):

    expenses = Expense.objects.filter(user=request.user)

    response = HttpResponse(content_type='text/csv')

    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'



    writer = csv.writer(response)

    writer.writerow(['Date', 'Title', 'Merchant', 'Category', 'Amount', 'Notes'])

    for e in expenses:

        writer.writerow([e.date, e.title, e.merchant, e.get_category_display(), e.amount, e.notes])

    return response





@login_required

def download_pdf(request):

    try:

        from reportlab.lib.pagesizes import letter

        from reportlab.lib import colors

        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        from reportlab.lib.styles import getSampleStyleSheet



        expenses = Expense.objects.filter(user=request.user)

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=letter)

        styles = getSampleStyleSheet()

        elements = []



        elements.append(Paragraph(f"Expense Report – {request.user.get_full_name() or request.user.username}", styles['Title']))

        elements.append(Paragraph(f"Generated: {datetime.date.today()}", styles['Normal']))

        elements.append(Spacer(1, 20))



        data = [['Date', 'Title', 'Merchant', 'Category', 'Amount']]

        total = Decimal('0')

        for e in expenses:

            data.append([str(e.date), e.title[:30], e.merchant[:20],

                         e.get_category_display(), f"${e.amount}"])

            total += e.amount

        data.append(['', '', '', 'TOTAL', f"${total}"])



        table = Table(data, colWidths=[70, 160, 110, 90, 70])

        table.setStyle(TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),

            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),

            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),

            ('FONTSIZE',   (0, 0), (-1, 0), 10),

            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f8f8')]),

            ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),

            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4e8')),

            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),

            ('TOPPADDING', (0, 0), (-1, -1), 6),

            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),

        ]))

        elements.append(table)

        doc.build(elements)



        buffer.seek(0)

        return HttpResponse(buffer, content_type='application/pdf',

                            headers={'Content-Disposition': 'attachment; filename="expenses.pdf"'})

    except ImportError:

        messages.error(request, 'PDF generation requires reportlab. Please install it.')

        return redirect('expense_list')

