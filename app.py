from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def to_float(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except ValueError:
        return 0.0

def to_int(v):
    try:
        return int(v) if v not in (None, "") else 0
    except ValueError:
        return 0

def compute_common(price, discount_amount, discount_rate, down_amount, down_rate):
    # discount
    if discount_amount > 0:
        discount_rate = (discount_amount / price) * 100 if price else 0
    else:
        discount_amount = price * (discount_rate / 100)
    discounted_price = price - discount_amount

    # down
    if down_amount > 0:
        down_rate = (down_amount / discounted_price) * 100 if discounted_price else 0
    else:
        down_amount = discounted_price * (down_rate / 100)

    loan_amount = discounted_price - down_amount
    return discounted_price, discount_amount, discount_rate, down_amount, down_rate, loan_amount

def calc_addon(loan_amount, interest_rate, years):
    months = years * 12
    total_interest = loan_amount * (interest_rate / 100.0) * years
    total_amount = loan_amount + total_interest
    monthly_payment = (total_amount / months) if months else 0.0
    return months, monthly_payment, total_interest, total_amount

def calc_effective(loan_amount, interest_rate, years):
    months = years * 12
    if months == 0:
        return 0, 0.0, 0.0, loan_amount
    rm = (interest_rate / 100.0) / 12.0
    if rm == 0:
        monthly = loan_amount / months
    else:
        monthly = loan_amount * rm / (1 - (1 + rm) ** (-months))
    total_amount = monthly * months
    total_interest = total_amount - loan_amount
    return months, monthly, total_interest, total_amount

def calculate(name, price, discount_amount, discount_rate, down_amount, down_rate, interest_rate, years, interest_type):
    discounted_price, disc_amt, disc_pct, down_amt, down_pct, loan_amount = compute_common(
        price, discount_amount, discount_rate, down_amount, down_rate
    )
    if interest_type == "effective":
        months, monthly_payment, total_interest, total_amount = calc_effective(loan_amount, interest_rate, years)
    else:
        interest_type = "addon"
        months, monthly_payment, total_interest, total_amount = calc_addon(loan_amount, interest_rate, years)

    return {
        "name": name,
        "original_price": price,
        "discount_amount": disc_amt,
        "discount_rate": disc_pct,
        "discounted_price": discounted_price,
        "down_amount": down_amt,
        "down_rate": down_pct,
        "interest_rate": interest_rate,
        "interest_type": interest_type,
        "loan_amount": loan_amount,
        "total_interest": total_interest,
        "total_amount": total_amount,
        "monthly_payment": monthly_payment,
        "months": months,
        "years": years,
    }

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    num_cars = to_int(request.args.get("num_cars", 1))
    if request.method == "POST":
        num_cars = to_int(request.form.get("num_cars", 1))
        for i in range(1, num_cars + 1):
            name = request.form.get(f"car_name{i}")
            price = to_float(request.form.get(f"car_price{i}", 0))
            disc_amt = to_float(request.form.get(f"discount_amount{i}", 0))
            disc_pct = to_float(request.form.get(f"discount_percent{i}", 0))
            down_amt = to_float(request.form.get(f"down_amount{i}", 0))
            down_pct = to_float(request.form.get(f"down_percent{i}", 0))
            rate = to_float(request.form.get(f"interest_rate{i}", 0))
            yrs = to_int(request.form.get(f"years{i}", 0))
            itype = request.form.get(f"interest_type{i}", "addon")
            if price <= 0 or yrs <= 0:
                continue
            results.append(calculate(name, price, disc_amt, disc_pct, down_amt, down_pct, rate, yrs, itype))
    return render_template("index.html", results=results, num_cars=num_cars)

@app.route("/api/amort", methods=["POST"])
def api_amort():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        loan_amount = to_float(payload.get("loan_amount"))
        interest_rate = to_float(payload.get("interest_rate"))
        months = to_int(payload.get("months"))
        interest_type = payload.get("interest_type", "addon")
        if months <= 0 or loan_amount <= 0:
            return jsonify({"rows": []})

        rows = []
        if interest_type == "effective":
            rm = (interest_rate / 100.0) / 12.0
            if rm == 0:
                monthly = loan_amount / months
            else:
                monthly = loan_amount * rm / (1 - (1 + rm) ** (-months))
            balance = loan_amount
            for k in range(1, months + 1):
                interest = balance * rm
                principal = monthly - interest
                if k == months:
                    principal = balance
                    monthly = principal + interest
                rows.append({
                    "k": k,
                    "balance": max(balance, 0.0),
                    "interest": max(interest, 0.0),
                    "principal": max(principal, 0.0),
                    "pay": max(monthly, 0.0),
                })
                balance = balance - principal
        else:
            # addon
            im = (loan_amount * (interest_rate / 100.0)) / 12.0
            months_addon, monthly, total_interest, total_amount = calc_addon(loan_amount, interest_rate, months // 12 if months % 12 == 0 else months / 12.0)
            principal_per_month = monthly - im
            for k in range(1, months + 1):
                balance_start = max(loan_amount - principal_per_month * (k - 1), 0.0)
                principal = principal_per_month if k < months else balance_start
                pay = principal + im if k < months else principal + im
                rows.append({
                    "k": k,
                    "balance": max(balance_start, 0.0),
                    "interest": max(im, 0.0),
                    "principal": max(principal, 0.0),
                    "pay": max(pay, 0.0),
                })

        return jsonify({"rows": rows})
    except Exception as e:
        return jsonify({"rows": [], "error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)
