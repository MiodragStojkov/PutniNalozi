from flask import Blueprint
from flask import  render_template, url_for, flash, redirect
from putninalozi import db
# from putninalozi.travel_warrants.forms import TravelWarrantForm
from putninalozi.models import TravelWarrant, User
from putninalozi.travel_warrants.forms import CreateTravelWarrantForm
from flask_login import login_user, login_required, logout_user, current_user


travel_warrants = Blueprint('travel_warrants', __name__)


@travel_warrants.route("/travel_warrant_list")
def travel_warrant_list():
    warrants = TravelWarrant.query.all()
    return render_template('travel_warrant_list.html', title='Travel Warrants', warrants=warrants)


@travel_warrants.route("/register_tw", methods=['GET', 'POST'])
def register_tw():
    # if current_user.is_authenticated:
    #     return redirect(url_for('main.home'))
    print(f'{current_user.user_company.id=}')
    users_list = User.query.filter_by(company_id=current_user.user_company.id).all()
    print(users_list)
    form = CreateTravelWarrantForm(users_list)
    if form.validate_on_submit():
        if current_user.authorization == 'c_admin':
            warrant = TravelWarrant(
                with_task=with_task.data,
                workplace=workplace.data,
                abroad=abroad.data,
                abroad_contry=abroad_contry.data,
                relation=relation.data,
                date_start=date_start.data,
                date_end=date_end.data,
                time_start=time_start.data,
                time_end=time_end.data,
                trip_approved_by=trip_approved_by.data,
                travel_expenses_paid_by=travel_expenses_paid_by.data,
                advance_payment_amount=advance_payment_amount.data,
                advance_payment_amount_currency=advance_payment_amount_currency.data,
                amount_of_daily_wages=amount_of_daily_wages.data,
                amount_of_daily_wages_currency=amount_of_daily_wages_currency.data,
                approve_usage_of=approve_usage_of.data,
                km_start=km_start.data,
                km_end=km_end.data,
                status=status.data,
                user_id=user_id.data,
                company_id=company_id.data
            )
            db.session.add(warrant)
            db.session.commit()
            flash(f'Travel Warrant: (!!!dodaj kod za broj putnog naloga!!!) has been created successfully!', 'success')
        elif current_user.authorization == 's_admin':
            warrant = TravelWarrant(
                with_task=with_task.data
            )
            db.session.add(warrant)
            db.session.commit()
    return render_template('register_tw.html', title='Create Travel Warrant', form=form)
