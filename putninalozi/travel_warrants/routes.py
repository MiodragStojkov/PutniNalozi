from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, abort, request, send_file
from putninalozi import db, bcrypt
from putninalozi.models import TravelWarrant, User, Vehicle, TravelWarrantExpenses, Company, Settings
from putninalozi.travel_warrants.forms import PreCreateTravelWarrantForm, CreateTravelWarrantForm, EditAdminTravelWarrantForm, EditUserTravelWarrantForm, TravelWarrantExpensesForm, EditTravelWarrantExpenses
from putninalozi.travel_warrants.pdf_form import create_pdf_form, update_pdf_fomr, send_email
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime


travel_warrants = Blueprint('travel_warrants', __name__)

def proracaun_broja_dnevnica(br_casova):
    if br_casova < 8:
        br_dnevnica = 0
        print(f'ispod 8h: {br_dnevnica=}')
    elif br_casova < 12:
        br_dnevnica = 0.5
        print(f'od 8h do 12h: {br_dnevnica=}')
    else:
        br_dnevnica = br_casova / 24
        print(f'proračun: {br_dnevnica=}')
        if br_dnevnica % 1 <= (8/24): #zaokruživanje na 0.5 (da li je 0-12h ili 8-12h)
            #zaokruži na x.0
            br_dnevnica = br_dnevnica // 1
            print(f'zaokruživanje na pola dnevnice: {br_dnevnica=}')
        elif br_dnevnica % 1 <= (12/24): #zaokruživanje na 0.5 (da li je 0-12h ili 8-12h)
            #zaokruži na x.5
            br_dnevnica = br_dnevnica // 1 + 0.5
            print(f'zaokruživanje na pola dnevnice: {br_dnevnica=}')
        else:
            #zaokruži na x+1
            br_dnevnica = br_dnevnica // 1 + 1
            print(f'zaokruživanje na celu dnevnicu: {br_dnevnica=}')
    return br_dnevnica

@travel_warrants.route("/download/<string:file_name>")
def download_file(file_name):
    file_name = file_name.replace('%20', ' ')
    path = "static/pdf_forms/" + file_name
    return send_file(path, as_attachment=True)


@travel_warrants.route("/travel_warrant_list", methods=['GET', 'POST'])
def travel_warrant_list():
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))

    warrants = TravelWarrant.query.all()
    form = PreCreateTravelWarrantForm()
    form.user_id.choices = [(0, '----------')] + [(u.id, u.name+ " " + u.surname) for u in db.session.query(User.id,User.name,User.surname).filter_by(company_id=current_user.user_company.id).order_by('name').all()]
    if form.validate_on_submit():
        korisnik_id = form.user_id.data
        datum = form.start_datetime.data
        return redirect(url_for('travel_warrants.register_tw',korisnik_id=korisnik_id, datum=datum))


    return render_template('travel_warrant_list.html', title='Putni nalozi', warrants=warrants, form=form, legend='Putni nalozi')


@travel_warrants.route("/register_tw/<int:korisnik_id>/<datum>", methods=['GET', 'POST'])
def register_tw(korisnik_id, datum):
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))

    if current_user.authorization == 'c_admin' or current_user.authorization == 's_admin':
        user_list = [(u.id, u.name+ " " + u.surname) for u in db.session.query(User.id,User.name,User.surname).filter_by(company_id=current_user.user_company.id).order_by('name').all()]
        print(user_list)
        vehicle_list = [('', '----------')] + [(v.id, v.vehicle_type + "-" + v.vehicle_brand+" ("+v.vehicle_registration+")") for v in db.session.query(Vehicle.id,Vehicle.vehicle_type,Vehicle.vehicle_brand,Vehicle.vehicle_registration).filter_by(company_id=current_user.user_company.id).order_by('vehicle_type').all()]
        datum = datum.replace('%20', ' ') #na sevreu zimeđu datuma i vremena se nalazi '%20' zbog toga ima ovaj replace


        print(f'{korisnik_id=}, {datum=}')
        datum = datetime.strptime(datum, '%Y-%m-%d %H:%M:%S') #'2022-09-27 15:02:00'
        print(type(datum))
        print(datum)

        drivers = [('', '----------')] + [(tw.travel_warrant_number, tw.travel_warrant_number + " => " + tw.travelwarrant_user.name + " " + tw.travelwarrant_user.surname + " - " + tw.travelwarrant_vehicle.vehicle_registration)
                                                for tw in TravelWarrant.query.filter(TravelWarrant.company_id==current_user.user_company.id,
                                                                                    TravelWarrant.vehicle_id!='').filter(TravelWarrant.start_datetime.between(
                                                                                                                    datum.replace(hour=0, minute=0, second=0, microsecond=0),
                                                                                                                    datum.replace(hour=23, minute=59, second=59, microsecond=9))).all()]
        print(drivers)

        ime_prezime = User.query.filter_by(id=korisnik_id).first().name + " " + User.query.filter_by(id=korisnik_id).first().surname
        print(ime_prezime)

        brojac = len(TravelWarrant.query.filter_by(company_id=current_user.user_company.id).filter(TravelWarrant.start_datetime.between(
                                                                                                            datum.replace(hour=0, minute=0, second=0, microsecond=0),
                                                                                                            datum.replace(hour=23, minute=59, second=59, microsecond=9))).all())

        if brojac + 1 < 10:
            brojac = '-0' + str(brojac + 1)
        else:
            brojac = '-' + str(brojac + 1)

        print(f'{korisnik_id=}, {datum=}, {brojac=}')
        podrazumevano_vozilo = User.query.filter_by(id=korisnik_id).first().default_vehicle
        print(f'{podrazumevano_vozilo=}')


        form = CreateTravelWarrantForm()
        form.reset()
        global_settings = Settings.query.filter_by(company_id=current_user.user_company.id).first()
        # form.user_id.choices = user_list
        # form.user_id.data = str(korisnik_id)
        form.vehicle_id.choices = vehicle_list
        form.together_with.choices = drivers
        if request.method == 'GET':
            form.vehicle_id.data  = str(podrazumevano_vozilo)
            form.costs_pays.data = 'poslodavca'
            form.daily_wage.data = global_settings.daily_wage_domestic
            form.daily_wage_abroad.data = global_settings.daily_wage_abroad
            if form.advance_payment.data == None:
                form.advance_payment.data = 0
        # form.start_datetime.data = datum
    else:
        flash('Nemate autorizaciju da kreirate putne naloge.', 'warning')
        return redirect(url_for('travel_warrants.travel_warrant_list'))

    if form.validate_on_submit():
        if form.together_with.data != '':
            warrant = TravelWarrant(
                user_id=korisnik_id,
                with_task=form.with_task.data,
                company_id=User.query.filter_by(id=korisnik_id).first().user_company.id,  #form.company_id.data,
                abroad_contry=form.abroad_contry.data.upper(),
                relation=form.relation.data,
                start_datetime=datum,
                end_datetime=form.end_datetime.data,
                vehicle_id=None,
                together_with=form.together_with.data,
                personal_type="",
                personal_brand="",
                personal_registration="",
                other="",
                advance_payment=form.advance_payment.data,
                advance_payment_currency=form.advance_payment_currency.data,
                daily_wage=form.daily_wage.data,
                daily_wage_currency=form.daily_wage_currency.data,
                daily_wage_abroad=form.daily_wage_abroad.data,
                daily_wage_abroad_currency=form.daily_wage_abroad_currency.data,
                costs_pays=form.costs_pays.data,
                km_start=1,
                km_end=1,
                status='kreiran',
                travel_warrant_number=datum.strftime('%Y%m%d') + brojac,
                file_name="",
                text_form="",
                expenses=[])
        elif form.personal_brand.data != "":
            warrant = TravelWarrant(
                user_id=korisnik_id,
                with_task=form.with_task.data,
                company_id=User.query.filter_by(id=korisnik_id).first().user_company.id,  #form.company_id.data,
                abroad_contry=form.abroad_contry.data.upper(),
                relation=form.relation.data,
                start_datetime=datum,
                end_datetime=form.end_datetime.data,
                vehicle_id=None,
                together_with="",
                personal_type=form.personal_type.data,
                personal_brand=form.personal_brand.data,
                personal_registration=form.personal_registration.data,
                other="",
                advance_payment=form.advance_payment.data,
                advance_payment_currency=form.advance_payment_currency.data,
                daily_wage=form.daily_wage.data,
                daily_wage_currency=form.daily_wage_currency.data,
                daily_wage_abroad=form.daily_wage_abroad.data,
                daily_wage_abroad_currency=form.daily_wage_abroad_currency.data,
                costs_pays=form.costs_pays.data,
                km_start=1,
                km_end=1,
                status='kreiran',
                travel_warrant_number=datum.strftime('%Y%m%d') + brojac,
                file_name="",
                text_form="",
                expenses=[])
        elif form.other.data != "":
            warrant = TravelWarrant(
                user_id=korisnik_id,
                with_task=form.with_task.data,
                company_id=User.query.filter_by(id=korisnik_id).first().user_company.id,  #form.company_id.data,
                abroad_contry=form.abroad_contry.data.upper(),
                relation=form.relation.data,
                start_datetime=datum,
                end_datetime=form.end_datetime.data,
                vehicle_id=None,
                together_with="",
                personal_type="",
                personal_brand="",
                personal_registration="",
                other=form.other.data,
                advance_payment=form.advance_payment.data,
                advance_payment_currency=form.advance_payment_currency.data,
                daily_wage=form.daily_wage.data,
                daily_wage_currency=form.daily_wage_currency.data,
                daily_wage_abroad=form.daily_wage_abroad.data,
                daily_wage_abroad_currency=form.daily_wage_abroad_currency.data,
                costs_pays=form.costs_pays.data,
                km_start=1,
                km_end=1,
                status='kreiran',
                travel_warrant_number=datum.strftime('%Y%m%d') + brojac,
                file_name="",
                text_form="",
                expenses=[])
        else:
            warrant = TravelWarrant(
                user_id=korisnik_id,
                with_task=form.with_task.data,
                company_id=User.query.filter_by(id=korisnik_id).first().user_company.id,  #form.company_id.data,
                abroad_contry=form.abroad_contry.data.upper(),
                relation=form.relation.data,
                start_datetime=datum,
                end_datetime=form.end_datetime.data,
                vehicle_id=form.vehicle_id.data,
                together_with="",
                personal_type="",
                personal_brand="",
                personal_registration="",
                other="",
                advance_payment=form.advance_payment.data,
                advance_payment_currency=form.advance_payment_currency.data,
                daily_wage=form.daily_wage.data,
                daily_wage_currency=form.daily_wage_currency.data,
                daily_wage_abroad=form.daily_wage_abroad.data,
                daily_wage_abroad_currency=form.daily_wage_abroad_currency.data,
                costs_pays=form.costs_pays.data,
                km_start=1,
                km_end=1,
                status='kreiran',
                travel_warrant_number=datum.strftime('%Y%m%d') + brojac,
                file_name="",
                text_form="",
                expenses=[])

        db.session.add(warrant)
        db.session.commit()

        br_casova = warrant.end_datetime - warrant.start_datetime
        print(f'razlika u vremenu {br_casova}')
        br_casova = br_casova.total_seconds() / 3600
        print(f'razlika u vremenu {br_casova} u satima')

        br_dnevnica = proracaun_broja_dnevnica(br_casova)

        file_name, text_form = create_pdf_form(warrant, br_casova, br_dnevnica)
        warrant.file_name = file_name
        warrant.text_form = text_form
        db.session.commit()
        print(text_form)
        print(file_name)

        print(f'{warrant.end_datetime=},{warrant.start_datetime=}')



        send_email(warrant, current_user, file_name)
        flash(f'Putni nalog broj: {warrant.travel_warrant_number} je uspešno kreiran!', 'success')
        flash(f'{warrant.travelwarrant_user.name} je {"dobio" if warrant.travelwarrant_user.gender == 1 else "dobila"} mejl sa detaljima putnog naloga.', 'success')
        return redirect(url_for('travel_warrants.travel_warrant_list'))

    return render_template('register_tw.html', title='Kreiranje putnog naloga',
                            legend='Kreiranje putnog naloga, zaposleni: ',
                            form=form, ime_prezime=ime_prezime, datum=datum)


@travel_warrants.route("/travel_warrant/<int:warrant_id>", methods=['GET', 'POST'])
def travel_warrant_profile(warrant_id):
    rod = []
    troskovi = TravelWarrantExpenses.query.filter_by(travelwarrant_id = warrant_id).all()
    warrant = TravelWarrant.query.get_or_404(warrant_id)
    if warrant.travelwarrant_user.gender == "1":
        rod=["Radnik", "raspoređen"]
    elif warrant.travelwarrant_user.gender == "2":
        rod=["Radnica", "raspoređena"]
    vehicle_list = [('', '----------')] + [(v.id, v.vehicle_type + "-" + v.vehicle_brand+" ("+v.vehicle_registration+")") for v in db.session.query(Vehicle.id,Vehicle.vehicle_type,Vehicle.vehicle_brand,Vehicle.vehicle_registration).filter_by(company_id=current_user.user_company.id).order_by('vehicle_type').all()]
    print(f'{vehicle_list=}')
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))
    elif current_user.authorization != 's_admin' and current_user.user_company.id != warrant.travelwarrant_company.id:
        abort(403)
    elif current_user.authorization == 'c_user' and current_user.id != warrant.travelwarrant_user.id:
        abort(403)

    if current_user.authorization != 'c_admin' and current_user.authorization != 's_admin':
        if warrant.status == 'storniran' or warrant.status == 'obračunat':
            return render_template('read_travel_warrant_user.html', title='Pregled putnog naloga', warrant=warrant, legend='Pregled putnog naloga', rod=rod, troskovi=troskovi)
        else:
            form = EditUserTravelWarrantForm()
            form.reset()
            drivers = [('', '----------')] + [(tw.travel_warrant_number, tw.travel_warrant_number + " => " + tw.travelwarrant_user.name + " " + tw.travelwarrant_user.surname)
                                                    for tw in TravelWarrant.query.filter(TravelWarrant.company_id==current_user.user_company.id,
                                                                                        TravelWarrant.vehicle_id!='').filter(TravelWarrant.start_datetime.between(
                                                                                                                        warrant.start_datetime.replace(hour=0, minute=0, second=0, microsecond=0),
                                                                                                                        warrant.start_datetime.replace(hour=23, minute=59, second=59, microsecond=9))).all()]
            form.together_with.choices = drivers
            # form.user_id.choices = [(u.id, u.name+ " " + u.surname) for u in db.session.query(User.id,User.name,User.surname).filter_by(company_id=current_user.user_company.id).group_by('name').all()]
            form.vehicle_id.choices = vehicle_list
            print(f'{form.vehicle_id.choices=}')
            form.personal_type.choices = [('', '----------'), ('AUTOMOBIL', 'AUTOMOBIL'),('KOMBI', 'KOMBI'),('KAMION', 'KAMION')]
            form.status.choices=[("kreiran", "kreiran"), ("završen", "završen")]

            if form.validate_on_submit():

                if form.together_with.data != '':
                    warrant.with_task = form.with_task.data
                    warrant.abroad_contry = form.abroad_contry.data
                    warrant.relation = form.relation.data

                    warrant.start_datetime = form.start_datetime.data
                    warrant.end_datetime = form.end_datetime.data
                    warrant.contry_leaving = form.contry_leaving.data
                    warrant.contry_return = form.contry_return.data

                    warrant.vehicle_id=None
                    warrant.together_with=form.together_with.data
                    warrant.personal_type=""
                    warrant.personal_brand=""
                    warrant.personal_registration=""
                    warrant.other=""

                    warrant.km_start = int(form.km_start.data)
                    warrant.km_end = int(form.km_end.data)
                    if request.form.get('dugme') == 'Završi':
                        warrant.status = 'završen'
                    else:
                        warrant.status = form.status.data

                    # warrant.expenses = form.expenses.data
                    print('zajedno sa - c_user')
                elif form.personal_brand.data != "":
                    warrant.with_task = form.with_task.data
                    warrant.abroad_contry = form.abroad_contry.data
                    warrant.relation = form.relation.data

                    warrant.start_datetime = form.start_datetime.data
                    warrant.end_datetime = form.end_datetime.data
                    warrant.contry_leaving = form.contry_leaving.data
                    warrant.contry_return = form.contry_return.data

                    warrant.vehicle_id=None
                    warrant.together_with=""
                    warrant.personal_type=form.personal_type.data
                    warrant.personal_brand=form.personal_brand.data
                    warrant.personal_registration=form.personal_registration.data
                    warrant.other=""

                    warrant.km_start = int(form.km_start.data)
                    warrant.km_end = int(form.km_end.data)
                    if request.form.get('dugme') == 'Završi':
                        warrant.status = 'završen'
                    else:
                        warrant.status = form.status.data

                    # warrant.expenses = form.expenses.data
                    print('licno vozilo - c_user')
                elif form.other.data != "":
                    warrant.with_task = form.with_task.data
                    warrant.abroad_contry = form.abroad_contry.data
                    warrant.relation = form.relation.data

                    warrant.start_datetime = form.start_datetime.data
                    warrant.end_datetime = form.end_datetime.data
                    warrant.contry_leaving = form.contry_leaving.data
                    warrant.contry_return = form.contry_return.data

                    warrant.vehicle_id=None
                    warrant.together_with=""
                    warrant.personal_type=""
                    warrant.personal_brand=""
                    warrant.personal_registration=""
                    warrant.other=form.other.data

                    warrant.km_start = int(form.km_start.data)
                    warrant.km_end = int(form.km_end.data)
                    if request.form.get('dugme') == 'Završi':
                        warrant.status = 'završen'
                    else:
                        warrant.status = form.status.data

                    # warrant.expenses = form.expenses.data
                    print('drugo - c_user')
                else:
                    warrant.with_task = form.with_task.data
                    warrant.abroad_contry = form.abroad_contry.data
                    warrant.relation = form.relation.data

                    warrant.start_datetime = form.start_datetime.data
                    warrant.end_datetime = form.end_datetime.data
                    warrant.contry_leaving = form.contry_leaving.data
                    warrant.contry_return = form.contry_return.data

                    warrant.vehicle_id=form.vehicle_id.data
                    warrant.together_with=""
                    warrant.personal_type=""
                    warrant.personal_brand=""
                    warrant.personal_registration=""
                    warrant.other=""

                    warrant.km_start = int(form.km_start.data)
                    warrant.km_end = int(form.km_end.data)
                    if request.form.get('dugme') == 'Završi':
                        warrant.status = 'završen'
                    else:
                        warrant.status = form.status.data

                    # warrant.expenses = form.expenses.data
                    print('službeno vozilo - c_user')
    ##########################################################################################

                br_casova = form.end_datetime.data - form.start_datetime.data
                print(f'razlika u vremenu {br_casova}')
                br_casova = br_casova.total_seconds() / 3600
                print(f'razlika u vremenu {br_casova} u satima')

                br_dnevnica = proracaun_broja_dnevnica(br_casova)

                file_name, text_form = create_pdf_form(warrant, br_casova, br_dnevnica)
                warrant.file_name = file_name
                warrant.text_form = text_form
                print(f'{warrant.end_datetime=},{warrant.start_datetime=}')

                db.session.commit()
    ##########################################################################################

                flash(f'Putni nalog {warrant.travel_warrant_number} je ažuriran.', 'success')
                return redirect(url_for('travel_warrants.travel_warrant_list'))
            elif request.method == 'GET':
                form.with_task.data = warrant.with_task
                form.abroad_contry.data = warrant.abroad_contry
                form.relation.data = warrant.relation
                form.start_datetime.data = warrant.start_datetime
                form.end_datetime.data = warrant.end_datetime
                form.contry_leaving.data = warrant.contry_leaving
                form.contry_return.data = warrant.contry_return
                form.vehicle_id.choices =[('', '----------')] + [(v.id, v.vehicle_type + "-" + v.vehicle_brand+" ("+v.vehicle_registration+")") for v in db.session.query(Vehicle.id,Vehicle.vehicle_type,Vehicle.vehicle_brand,Vehicle.vehicle_registration).filter_by(company_id=current_user.user_company.id).order_by('vehicle_type').all()]
                form.vehicle_id.data = str(warrant.vehicle_id)
                form.together_with.data = warrant.together_with
                form.personal_type.choices = [('', '----------'), ('AUTOMOBIL', 'AUTOMOBIL'),('KOMBI', 'KOMBI'),('KAMION', 'KAMION')]
                form.personal_type.data = warrant.personal_type
                form.personal_brand.data = warrant.personal_brand
                form.personal_registration.data = warrant.personal_registration
                form.other.data = warrant.other

                form.km_start.data = warrant.km_start
                form.km_end.data = warrant.km_end
                form.status.choices=[("kreiran", "kreiran"), ("završen", "završen")]
                form.status.data = str(warrant.status)

                # form.expenses.data = warrant.expenses

            print(f'EditUser: {form.errors=}')

            return render_template('travel_warrant_user.html', title='Uređivanje putnog naloga', warrant=warrant, legend='Uređivanje putnog naloga (pregled korisnika)', form=form, rod=rod, troskovi=troskovi)

    else:
        form = EditAdminTravelWarrantForm()
        form.reset()
        drivers = [('', '----------')] + [(tw.travel_warrant_number, tw.travel_warrant_number + " => " + tw.travelwarrant_user.name + " " + tw.travelwarrant_user.surname)
                                                for tw in TravelWarrant.query.filter(TravelWarrant.company_id==current_user.user_company.id,
                                                                                    TravelWarrant.vehicle_id!='').filter(TravelWarrant.start_datetime.between(
                                                                                                                    warrant.start_datetime.replace(hour=0, minute=0, second=0, microsecond=0),
                                                                                                                    warrant.start_datetime.replace(hour=23, minute=59, second=59, microsecond=9))).all()]
        form.together_with.choices = drivers

        # form.user_id.choices = [(u.id, u.name+ " " + u.surname) for u in db.session.query(User.id,User.name,User.surname).filter_by(company_id=current_user.user_company.id).order_by('name').all()]
        form.vehicle_id.choices = vehicle_list
        print(f'{form.vehicle_id.choices=}')
        form.personal_type.choices = [('', '----------'), ('AUTOMOBIL', 'AUTOMOBIL'),('KOMBI', 'KOMBI'),('KAMION', 'KAMION')]
        form.status.choices=[("kreiran", "kreiran"), ("završen", "završen"), ("obračunat", "obračunat"), ("storniran", "storniran")]

        if form.validate_on_submit():
            if form.together_with.data != '':
                # warrant.user_id = form.user_id.data
                warrant.with_task = form.with_task.data
                # warrant.company_id = int(form.company_id.data)
                warrant.abroad_contry = form.abroad_contry.data
                warrant.relation = form.relation.data

                warrant.start_datetime = form.start_datetime.data
                warrant.end_datetime = form.end_datetime.data
                warrant.contry_leaving = form.contry_leaving.data
                warrant.contry_return = form.contry_return.data

                warrant.vehicle_id=None
                warrant.together_with=form.together_with.data
                warrant.personal_type=""
                warrant.personal_brand=""
                warrant.personal_registration=""
                warrant.other=""

                warrant.advance_payment = int(form.advance_payment.data)
                warrant.advance_payment_currency = form.advance_payment_currency.data
                warrant.daily_wage = form.daily_wage.data
                warrant.daily_wage_currency = form.daily_wage_currency.data
                warrant.daily_wage_abroad = form.daily_wage_abroad.data
                warrant.daily_wage_abroad_currency = form.daily_wage_abroad_currency.data
                warrant.costs_pays = form.costs_pays.data

                warrant.km_start = int(form.km_start.data)
                warrant.km_end = int(form.km_end.data)
                if request.form.get('dugme') == 'Završi':
                    warrant.status = 'završen'
                elif request.form.get('dugme') == 'Obračunajte':
                    warrant.status = 'obračunat'
                else:
                    warrant.status = form.status.data

                # warrant.expenses = form.expenses.data
                print('zajedno sa')
            elif form.personal_brand.data != "":
                # warrant.user_id = form.user_id.data
                warrant.with_task = form.with_task.data
                # warrant.company_id = int(form.company_id.data)
                warrant.abroad_contry = form.abroad_contry.data
                warrant.relation = form.relation.data

                warrant.start_datetime = form.start_datetime.data
                warrant.end_datetime = form.end_datetime.data
                warrant.contry_leaving = form.contry_leaving.data
                warrant.contry_return = form.contry_return.data

                warrant.vehicle_id=None
                warrant.together_with=""
                warrant.personal_type=form.personal_type.data
                warrant.personal_brand=form.personal_brand.data
                warrant.personal_registration=form.personal_registration.data
                warrant.other=""

                warrant.advance_payment = int(form.advance_payment.data)
                warrant.advance_payment_currency = form.advance_payment_currency.data
                warrant.daily_wage = int(form.daily_wage.data)
                warrant.daily_wage_currency = form.daily_wage_currency.data
                warrant.daily_wage_abroad = form.daily_wage_abroad.data
                warrant.daily_wage_abroad_currency = form.daily_wage_abroad_currency.data
                warrant.costs_pays = form.costs_pays.data

                warrant.km_start = int(form.km_start.data)
                warrant.km_end = int(form.km_end.data)
                if request.form.get('dugme') == 'Završi':
                    warrant.status = 'završen'
                elif request.form.get('dugme') == 'Obračunajte':
                    warrant.status = 'obračunat'
                else:
                    warrant.status = form.status.data

                # warrant.expenses = form.expenses.data
                print('lično vozilo')
            elif form.other.data != "":
                # warrant.user_id = form.user_id.data
                warrant.with_task = form.with_task.data
                # warrant.company_id = int(form.company_id.data)
                warrant.abroad_contry = form.abroad_contry.data
                warrant.relation = form.relation.data

                warrant.start_datetime = form.start_datetime.data
                warrant.end_datetime = form.end_datetime.data
                warrant.contry_leaving = form.contry_leaving.data
                warrant.contry_return = form.contry_return.data

                warrant.vehicle_id=None
                warrant.together_with=""
                warrant.personal_type=""
                warrant.personal_brand=""
                warrant.personal_registration=""
                warrant.other=form.other.data

                warrant.advance_payment = int(form.advance_payment.data)
                warrant.advance_payment_currency = form.advance_payment_currency.data
                warrant.daily_wage = int(form.daily_wage.data)
                warrant.daily_wage_currency = form.daily_wage_currency.data
                warrant.daily_wage_abroad = form.daily_wage_abroad.data
                warrant.daily_wage_abroad_currency = form.daily_wage_abroad_currency.data
                warrant.costs_pays = form.costs_pays.data

                warrant.km_start = int(form.km_start.data)
                warrant.km_end = int(form.km_end.data)
                if request.form.get('dugme') == 'Završi':
                    warrant.status = 'završen'
                elif request.form.get('dugme') == 'Obračunajte':
                    warrant.status = 'obračunat'
                else:
                    warrant.status = form.status.data

                # warrant.expenses = form.expenses.data
                print('drugo')
            else:
                # warrant.user_id = form.user_id.data
                warrant.with_task = form.with_task.data
                # warrant.company_id = int(form.company_id.data)
                warrant.abroad_contry = form.abroad_contry.data
                warrant.relation = form.relation.data

                warrant.start_datetime = form.start_datetime.data
                warrant.end_datetime = form.end_datetime.data
                warrant.contry_leaving = form.contry_leaving.data
                warrant.contry_return = form.contry_return.data

                warrant.vehicle_id=form.vehicle_id.data
                warrant.together_with=""
                warrant.personal_type=""
                warrant.personal_brand=""
                warrant.personal_registration=""
                warrant.other=""

                warrant.advance_payment = int(form.advance_payment.data)
                warrant.advance_payment_currency = form.advance_payment_currency.data
                warrant.daily_wage = int(form.daily_wage.data)
                warrant.daily_wage_currency = form.daily_wage_currency.data
                warrant.daily_wage_abroad = form.daily_wage_abroad.data
                warrant.daily_wage_abroad_currency = form.daily_wage_abroad_currency.data
                warrant.costs_pays = form.costs_pays.data

                warrant.km_start = int(form.km_start.data)
                warrant.km_end = int(form.km_end.data)
                if request.form.get('dugme') == 'Završi':
                    warrant.status = 'završen'
                elif request.form.get('dugme') == 'Obračunajte':
                    warrant.status = 'obračunat'
                else:
                    warrant.status = form.status.data

                # warrant.expenses = []
                print('službeno vozilo')

##########################################################################################
            br_casova = form.end_datetime.data - form.start_datetime.data
            print(f'razlika u vremenu {br_casova}')
            br_casova = br_casova.total_seconds() / 3600
            print(f'razlika u vremenu {br_casova} u satima')

            br_dnevnica = proracaun_broja_dnevnica(br_casova)

            file_name, text_form = update_pdf_fomr(warrant, br_casova, br_dnevnica, troskovi)
            warrant.file_name = file_name
            warrant.text_form = text_form
            print(f'{warrant.end_datetime=},{warrant.start_datetime=}')

            db.session.commit()
##########################################################################################

            db.session.commit()
            flash(f'Putni nalog {warrant.travel_warrant_number} je ažuriran.', 'success')
            return redirect(url_for('travel_warrants.travel_warrant_list'))
        elif request.method == 'GET':
            # form.user_id.choices = [(u.id, u.name+ " " + u.surname) for u in db.session.query(User.id,User.name,User.surname).filter_by(company_id=current_user.user_company.id).order_by('name').all()]
            # form.user_id.data = warrant.user_id
            form.with_task.data = warrant.with_task
            # form.company_id.data = str(User.query.filter_by(id=form.user_id.data).first().user_company.id)
            form.abroad_contry.data = warrant.abroad_contry
            form.relation.data = warrant.relation
            form.start_datetime.data = warrant.start_datetime
            form.end_datetime.data = warrant.end_datetime
            form.contry_leaving.data = warrant.contry_leaving
            form.contry_return.data = warrant.contry_return
            form.vehicle_id.data = str(warrant.vehicle_id)
            form.together_with.data = warrant.together_with
            form.personal_type.choices = [('', '----------'), ('AUTOMOBIL', 'AUTOMOBIL'),('KOMBI', 'KOMBI'),('KAMION', 'KAMION')]
            form.personal_type.data = warrant.personal_type
            form.personal_brand.data = warrant.personal_brand
            form.personal_registration.data = warrant.personal_registration
            form.other.data = warrant.other

            form.advance_payment.data = warrant.advance_payment
            form.advance_payment_currency.data = warrant.advance_payment_currency
            form.daily_wage.data = warrant.daily_wage
            form.daily_wage_currency.data = warrant.daily_wage_currency
            form.daily_wage_abroad.data = warrant.daily_wage_abroad
            form.daily_wage_abroad_currency.data = warrant.daily_wage_abroad_currency
            form.costs_pays.data = warrant.costs_pays
            form.km_start.data = warrant.km_start
            form.km_end.data = warrant.km_end
            form.status.choices=[("kreiran", "kreiran"), ("završen", "završen"), ("obračunat", "obračunat") , ("storniran", "storniran")]
            form.status.data = str(warrant.status)

            # form.expenses.data = "prazna lista za početak"

        print(f'EditAdmin: {form.errors=}')

        return render_template('travel_warrant.html', title='Uređivanje putnog naloga', warrant=warrant, legend='Uređivanje putnog naloga (pregled administratora)', form=form, rod=rod, troskovi=troskovi)


@travel_warrants.route("/add_expenses/<int:warrant_id>", methods=['GET', 'POST'])
def add_expenses(warrant_id):
    troskovi = TravelWarrantExpenses.query.filter_by(travelwarrant_id = warrant_id).all()
    warrant = TravelWarrant.query.get_or_404(warrant_id)
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))
    elif current_user.user_company.id != warrant.company_id:
            abort(403)
    form = TravelWarrantExpensesForm()
    if form.validate_on_submit():
        expense = TravelWarrantExpenses(expenses_type = form.expenses_type.data,
                expenses_date = form.expenses_date.data,
                description = form.description.data,
                amount = form.amount.data,
                amount_currency = form.amount_currency.data,
                travelwarrant_id = warrant_id)
        db.session.add(expense)
        db.session.commit()
        flash(f'U putnom nalogu broj {warrant.travel_warrant_number} je dodat trošak - {expense.expenses_type}.', 'success')
        return redirect(url_for('travel_warrants.travel_warrant_profile', warrant_id=warrant_id))


    print(troskovi)
    print(warrant)
    return render_template('expenses.html', form=form, legend='Dodavanje troškova:', warrant=warrant, troskovi=troskovi)


@travel_warrants.route("/expenses/<int:warrant_id>/<int:expenses_id>", methods=['GET', 'POST'])
def expenses_profile(warrant_id, expenses_id): #ovo je funkcija a editovnaje troškova
    expense = TravelWarrantExpenses.query.get_or_404(expenses_id)
    troskovi = TravelWarrantExpenses.query.filter_by(travelwarrant_id = warrant_id).all()
    warrant = TravelWarrant.query.get_or_404(warrant_id)
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))
    elif current_user.user_company.id != warrant.company_id:
            abort(403)
    form = EditTravelWarrantExpenses()
    form.reset()
    form.expenses_type.choices=[('Ostale naknade', 'Ostale naknade'), ('Ostali troškovi na službenom putu', 'Ostali troškovi na službenom putu'), ('Parkiranje', 'Parkiranje'), ('Putarine', 'Putarine'), ('Troškovi noćenja', 'Troškovi noćenja'), ('Troškovi prevoza', 'Troškovi prevoza'), ('Troškovi smeštaja i ishrane', 'Troškovi smeštaja i ishrane')]
    if form.validate_on_submit():
        expense.expenses_type = form.expenses_type.data
        expense.expenses_date = form.expenses_date.data
        expense.description = form.description.data
        expense.amount = form.amount.data
        expense.amount_currency = form.amount_currency.data
        db.session.commit()
        flash(f'Uspešno je ažuriran trošak: {expense.expenses_type}.', 'success')
        return redirect(url_for('travel_warrants.travel_warrant_profile', warrant_id=warrant_id))
    elif request.method == 'GET':
        form.expenses_type.data = str(expense.expenses_type)
        form.expenses_date.data = expense.expenses_date
        form.description.data = expense.description
        form.amount.data = expense.amount
        form.amount_currency.data = expense.amount_currency
    return render_template('expenses.html', form=form, legend='Uređivanje troška:', warrant=warrant, troskovi=troskovi, expense=expense)


@travel_warrants.route("/expenses/<int:warrant_id>/<int:expenses_id>/delete", methods=['GET', 'POST'])
# @login_required
def delete_expense(warrant_id, expenses_id):
    expense = TravelWarrantExpenses.query.get_or_404(expenses_id)
    warrant = TravelWarrant.query.get_or_404(warrant_id)
    print(expense)
    print(warrant)
    if not current_user.is_authenticated:
        flash('Da biste pristupili ovoj stranici treba da budete ulogovani.', 'danger')
        return redirect(url_for('users.login'))
    elif current_user.user_company.id != warrant.company_id: #ako putni nalog nije iz kompanije trenutno ulogovanok korisnika
            abort(403)
    else:
        db.session.delete(expense)
        db.session.commit()
        flash(f'Trošak {expense.expenses_type} je obrisan.', 'success' )
        return redirect(url_for('travel_warrants.travel_warrant_profile', warrant_id=warrant_id))
