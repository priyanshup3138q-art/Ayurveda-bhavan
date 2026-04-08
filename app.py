from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, date, timedelta
from functools import wraps
import os, json, hmac, hashlib

app = Flask(__name__)
app.secret_key = 'ayurveda-bhavan-secret-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ayurveda_bhavan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

RAZORPAY_KEY_ID     = os.environ.get('RAZORPAY_KEY_ID',     'rzp_test_XXXXXXXXXX')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'your_secret_here')
MAIL_SERVER         = 'smtp.gmail.com'
MAIL_PORT           = 587
MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', 'your@gmail.com')
MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', 'your_app_password')
GOOGLE_MAPS_KEY     = os.environ.get('GOOGLE_MAPS_KEY', 'YOUR_GOOGLE_MAPS_API_KEY')

db     = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ══════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════

class User(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(100), nullable=False)
    email     = db.Column(db.String(150), unique=True, nullable=False)
    password  = db.Column(db.String(200), nullable=False)
    phone     = db.Column(db.String(15))
    role      = db.Column(db.String(20), default='customer')
    created_at= db.Column(db.DateTime, default=datetime.utcnow)
    bookings  = db.relationship('Booking', backref='user', lazy=True, foreign_keys='Booking.user_id')
    hotels    = db.relationship('Hotel', backref='owner', lazy=True)
    reviews   = db.relationship('Review', backref='user', lazy=True)
    support_tickets = db.relationship('SupportTicket', backref='user', lazy=True)

class Hotel(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    owner_id            = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name                = db.Column(db.String(150), nullable=False)
    city                = db.Column(db.String(100), nullable=False)
    state               = db.Column(db.String(100))
    address             = db.Column(db.String(300))
    latitude            = db.Column(db.Float, default=0.0)
    longitude           = db.Column(db.Float, default=0.0)
    description         = db.Column(db.Text)
    price_per_night     = db.Column(db.Float, nullable=False)
    rating              = db.Column(db.Float, default=0.0)
    total_reviews       = db.Column(db.Integer, default=0)
    category            = db.Column(db.String(50))
    amenities           = db.Column(db.String(500))
    is_verified         = db.Column(db.Boolean, default=False)
    last_verified_date  = db.Column(db.Date)
    commission_rate     = db.Column(db.Float, default=10.0)
    cancellation_policy = db.Column(db.String(50), default='moderate')
    is_available        = db.Column(db.Boolean, default=True)
    rooms               = db.relationship('Room', backref='hotel', lazy=True)
    reviews_rel         = db.relationship('Review', backref='hotel', lazy=True)
    payouts             = db.relationship('Payout', backref='hotel', lazy=True)

class Room(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    hotel_id        = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    room_type       = db.Column(db.String(50))
    capacity        = db.Column(db.Integer, default=2)
    price_per_night = db.Column(db.Float)
    is_available    = db.Column(db.Boolean, default=True)
    bookings        = db.relationship('Booking', backref='room', lazy=True)

class Booking(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id             = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in            = db.Column(db.Date, nullable=False)
    check_out           = db.Column(db.Date, nullable=False)
    guests              = db.Column(db.Integer, default=1)
    base_price          = db.Column(db.Float)
    gst_amount          = db.Column(db.Float)
    total_price         = db.Column(db.Float)
    platform_fee        = db.Column(db.Float)
    hotel_payout        = db.Column(db.Float)
    status              = db.Column(db.String(20), default='pending')
    cancel_reason       = db.Column(db.String(300))
    refund_amount       = db.Column(db.Float, default=0)
    razorpay_order_id   = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    payment_status      = db.Column(db.String(20), default='pending')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def hotel(self):
        return self.room.hotel

class Review(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hotel_id         = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    booking_id       = db.Column(db.Integer, db.ForeignKey('booking.id'))
    rating           = db.Column(db.Integer)
    comment          = db.Column(db.Text)
    is_verified_stay = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

class Payout(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    hotel_id   = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount     = db.Column(db.Float)
    status     = db.Column(db.String(20), default='scheduled')
    due_date   = db.Column(db.Date)
    paid_date  = db.Column(db.Date)
    utr_number = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SupportTicket(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=True)
    subject    = db.Column(db.String(200))
    message    = db.Column(db.Text)
    status     = db.Column(db.String(20), default='open')
    priority   = db.Column(db.String(20), default='normal')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Pehle login karein!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'hotel_owner':
            flash('Sirf hotel owners ke liye!', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

def calculate_pricing(base_price, nights, commission_rate=10.0):
    subtotal     = base_price * nights
    gst_rate     = 0.12 if base_price < 7500 else 0.18
    gst_amount   = round(subtotal * gst_rate, 2)
    total        = round(subtotal + gst_amount, 2)
    platform_fee = round(subtotal * commission_rate / 100, 2)
    hotel_payout = round(subtotal - platform_fee, 2)
    return {'subtotal': subtotal, 'gst_rate': gst_rate * 100,
            'gst_amount': gst_amount, 'total': total,
            'platform_fee': platform_fee, 'hotel_payout': hotel_payout}

def calculate_refund(booking):
    days_before = (booking.check_in - date.today()).days
    policy = booking.hotel.cancellation_policy
    if policy == 'flexible':
        if days_before >= 1: return booking.base_price, '100% refund'
        return 0, 'No refund'
    elif policy == 'moderate':
        if days_before >= 5:  return booking.base_price, '100% refund'
        if days_before >= 2:  return booking.base_price * 0.5, '50% refund'
        return 0, 'No refund'
    else:
        if days_before >= 14: return booking.base_price, '100% refund'
        if days_before >= 7:  return booking.base_price * 0.5, '50% refund'
        return 0, 'No refund — strict policy'

def send_email(to_email, subject, body_html):
    """✅ Gmail SMTP se email"""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'Ayurveda Bhavan <{MAIL_USERNAME}>'
        msg['To']      = to_email
        msg.attach(MIMEText(body_html, 'html'))
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, to_email, msg.as_string())
        print(f'✅ Email sent to {to_email}')
        return True
    except Exception as e:
        print(f'⚠️ Email error (configure MAIL_USERNAME/PASSWORD): {e}')
        return False

def send_booking_confirmation(booking):
    subject = f'Ayurveda Bhavan — Booking #{booking.id} Confirmed! 🌿'
    body = f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;padding:30px">
      <div style="background:linear-gradient(135deg,#0e2e1a,#0e1a2e);padding:30px;border-radius:16px;text-align:center;margin-bottom:24px">
        <h1 style="color:#fff;margin:0">🌿 Ayurveda Bhavan</h1>
        <p style="color:rgba(255,255,255,.6);margin:8px 0 0">Booking Confirmed!</p>
      </div>
      <h2>Namaste {booking.user.name}! 🙏</h2>
      <div style="background:#f8f7fc;border-radius:12px;padding:20px;margin:20px 0">
        <table style="width:100%;font-size:14px;border-collapse:collapse">
          <tr><td style="padding:8px 0;color:#70708a">Hotel</td><td><b>{booking.hotel.name}</b></td></tr>
          <tr><td style="padding:8px 0;color:#70708a">Location</td><td>{booking.hotel.city}, {booking.hotel.state}</td></tr>
          <tr><td style="padding:8px 0;color:#70708a">Check-in</td><td><b>{booking.check_in.strftime('%d %B %Y')}</b></td></tr>
          <tr><td style="padding:8px 0;color:#70708a">Check-out</td><td><b>{booking.check_out.strftime('%d %B %Y')}</b></td></tr>
          <tr><td style="padding:8px 0;color:#70708a">Nights</td><td>{booking.nights}</td></tr>
          <tr><td style="padding:8px 0;color:#70708a">Guests</td><td>{booking.guests}</td></tr>
          <tr style="border-top:1px solid #e4e2f0"><td style="padding:12px 0;font-weight:600">Total Paid</td><td style="font-size:18px;font-weight:700">₹{int(booking.total_price)}</td></tr>
        </table>
      </div>
      <p style="color:#70708a;font-size:13px">GST included. Koi hidden charges nahi. 🌿</p>
    </div>"""
    send_email(booking.user.email, subject, body)

def create_razorpay_order(amount_rupees):
    """✅ Razorpay order — razorpay library install karni hogi"""
    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        return client.order.create({'amount': int(amount_rupees * 100), 'currency': 'INR', 'payment_capture': 1})
    except Exception as e:
        print(f'⚠️ Razorpay error (configure keys): {e}')
        return None

def verify_razorpay_sig(order_id, payment_id, signature):
    key      = f'{order_id}|{payment_id}'.encode()
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), key, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def create_payout(booking):
    p = Payout(hotel_id=booking.hotel.id, booking_id=booking.id,
               amount=booking.hotel_payout, status='scheduled',
               due_date=booking.check_in + timedelta(days=1))
    db.session.add(p)

@app.context_processor
def inject_globals():
    return {'today': date.today(), 'maps_key': GOOGLE_MAPS_KEY}

# ══════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        phone    = request.form.get('phone', '')
        role     = request.form.get('role', 'customer')
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        user = User(name=name, email=email, phone=phone, role=role, password=password)
        db.session.add(user)
        db.session.commit()
        session.update({'user_id': user.id, 'user_name': user.name, 'role': user.role, 'user_email': email})
        send_email(email, '🌿 Ayurveda Bhavan mein Swagat!',
                   f'<h2>Namaste {name}! 🙏</h2><p>Ayurveda Bhavan mein aapka swagat hai.</p>')
        flash(f'Welcome {name}! 🌿', 'success')
        return redirect(url_for('owner_dashboard') if role == 'hotel_owner' else url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            session.update({'user_id': user.id, 'user_name': user.name,
                            'role': user.role, 'user_email': user.email})
            flash(f'Welcome back, {user.name}! 🌿', 'success')
            return redirect(url_for('owner_dashboard') if user.role == 'hotel_owner' else url_for('home'))
        flash('Email ya password galat hai!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ══════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════

@app.route('/')
def home():
    hotels = Hotel.query.filter_by(is_available=True).order_by(Hotel.rating.desc()).limit(8).all()
    return render_template('home.html', hotels=hotels)

@app.route('/search')
def search():
    city      = request.args.get('city', '')
    check_in  = request.args.get('check_in', '')
    check_out = request.args.get('check_out', '')
    guests    = request.args.get('guests', 1, type=int)
    category  = request.args.get('category', '')
    min_price = request.args.get('min_price', 0, type=float)
    max_price = request.args.get('max_price', 99999, type=float)
    sort      = request.args.get('sort', 'rating')
    q = Hotel.query.filter_by(is_available=True)
    if city:     q = q.filter(Hotel.city.ilike(f'%{city}%'))
    if category: q = q.filter_by(category=category)
    q = q.filter(Hotel.price_per_night.between(min_price, max_price))
    if sort == 'price_asc':    q = q.order_by(Hotel.price_per_night.asc())
    elif sort == 'price_desc': q = q.order_by(Hotel.price_per_night.desc())
    else:                      q = q.order_by(Hotel.rating.desc())
    return render_template('search.html', hotels=q.all(), city=city,
                           check_in=check_in, check_out=check_out, guests=guests, sort=sort)

@app.route('/hotel/<int:hotel_id>')
def hotel_detail(hotel_id):
    hotel     = Hotel.query.get_or_404(hotel_id)
    rooms     = Room.query.filter_by(hotel_id=hotel_id, is_available=True).all()
    reviews   = Review.query.filter_by(hotel_id=hotel_id).order_by(Review.created_at.desc()).limit(12).all()
    amenities = hotel.amenities.split(',') if hotel.amenities else []
    can_review = False
    if 'user_id' in session:
        stayed  = (Booking.query.join(Room).filter(Room.hotel_id==hotel_id,
                   Booking.user_id==session['user_id'], Booking.status=='completed').first())
        already = Review.query.filter_by(user_id=session['user_id'], hotel_id=hotel_id).first()
        can_review = bool(stayed and not already)
    return render_template('hotel_detail.html', hotel=hotel, rooms=rooms, reviews=reviews,
                           amenities=amenities, can_review=can_review,
                           check_in=request.args.get('check_in',''),
                           check_out=request.args.get('check_out',''))

# ══════════════════════════════════════════════
#  BOOKING — RAZORPAY FLOW
# ══════════════════════════════════════════════

@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    room  = Room.query.get_or_404(room_id)
    hotel = room.hotel
    if request.method == 'POST':
        check_in  = datetime.strptime(request.form['check_in'],  '%Y-%m-%d').date()
        check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
        guests    = request.form.get('guests', 1, type=int)
        nights    = (check_out - check_in).days
        if nights <= 0:
            flash('Check-out must be after check-in!', 'danger')
            return redirect(request.url)
        conflict = Booking.query.filter(
            Booking.room_id==room_id, Booking.status.in_(['pending','confirmed']),
            Booking.check_in<check_out, Booking.check_out>check_in).first()
        if conflict:
            flash('Yeh room in dates pe already booked hai!', 'danger')
            return redirect(request.url)
        pricing  = calculate_pricing(room.price_per_night, nights, hotel.commission_rate)
        rz_order = create_razorpay_order(pricing['total'])
        booking  = Booking(
            user_id=session['user_id'], room_id=room_id,
            check_in=check_in, check_out=check_out, guests=guests,
            base_price=pricing['subtotal'], gst_amount=pricing['gst_amount'],
            total_price=pricing['total'], platform_fee=pricing['platform_fee'],
            hotel_payout=pricing['hotel_payout'],
            razorpay_order_id=rz_order['id'] if rz_order else None,
            status='pending', payment_status='pending')
        db.session.add(booking)
        db.session.commit()
        if rz_order:
            return render_template('payment.html', booking=booking, hotel=hotel,
                                   rz_order=rz_order, rz_key=RAZORPAY_KEY_ID, pricing=pricing)
        # Dev fallback — no Razorpay keys configured
        booking.status = 'confirmed'
        booking.payment_status = 'paid'
        db.session.commit()
        create_payout(booking)
        db.session.commit()
        send_booking_confirmation(booking)
        flash('Booking confirmed! 🌿 Email bheja gaya.', 'success')
        return redirect(url_for('booking_detail', booking_id=booking.id))

    check_in_str  = request.args.get('check_in', '')
    check_out_str = request.args.get('check_out', '')
    pricing_preview = None
    if check_in_str and check_out_str:
        try:
            n = (datetime.strptime(check_out_str,'%Y-%m-%d').date() -
                 datetime.strptime(check_in_str,'%Y-%m-%d').date()).days
            if n > 0:
                pricing_preview = calculate_pricing(room.price_per_night, n, hotel.commission_rate)
                pricing_preview['nights'] = n
        except: pass
    return render_template('book_room.html', room=room, hotel=hotel,
                           pricing=pricing_preview, check_in=check_in_str, check_out=check_out_str)

@app.route('/payment/verify', methods=['POST'])
@login_required
def verify_payment():
    data       = request.get_json()
    booking    = Booking.query.get_or_404(data.get('booking_id'))
    if verify_razorpay_sig(data.get('razorpay_order_id'),
                           data.get('razorpay_payment_id'),
                           data.get('razorpay_signature')):
        booking.razorpay_payment_id = data.get('razorpay_payment_id')
        booking.status              = 'confirmed'
        booking.payment_status      = 'paid'
        db.session.commit()
        create_payout(booking)
        db.session.commit()
        send_booking_confirmation(booking)
        return jsonify({'success': True, 'redirect': url_for('booking_detail', booking_id=booking.id)})
    booking.status = 'cancelled'
    booking.payment_status = 'failed'
    db.session.commit()
    return jsonify({'success': False}), 400

@app.route('/booking/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != session['user_id']:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('my_bookings'))
    payout = Payout.query.filter_by(booking_id=booking_id).first()
    return render_template('booking_detail.html', booking=booking, payout=payout)

@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/cancel/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != session['user_id']:
        flash('Unauthorized!', 'danger')
        return redirect(url_for('my_bookings'))
    refund_amount, refund_msg = calculate_refund(booking)
    if request.method == 'POST':
        booking.status        = 'cancelled'
        booking.cancel_reason = request.form.get('reason', '')
        booking.refund_amount = refund_amount
        payout = Payout.query.filter_by(booking_id=booking_id).first()
        if payout and payout.status == 'scheduled':
            payout.status = 'cancelled'
        db.session.commit()
        send_email(booking.user.email, f'Booking #{booking.id} Cancel — Ayurveda Bhavan',
                   f'<h2>Booking Cancel Ho Gayi</h2><p>Refund: ₹{int(refund_amount)} — {refund_msg}</p>')
        flash(f'Booking cancel ho gayi. Refund: ₹{int(refund_amount)} — {refund_msg}', 'info')
        return redirect(url_for('my_bookings'))
    return render_template('cancel_booking.html', booking=booking,
                           refund_amount=refund_amount, refund_msg=refund_msg)

# ══════════════════════════════════════════════
#  REVIEWS
# ══════════════════════════════════════════════

@app.route('/review/<int:hotel_id>', methods=['POST'])
@login_required
def add_review(hotel_id):
    stayed = (Booking.query.join(Room).filter(Room.hotel_id==hotel_id,
              Booking.user_id==session['user_id'], Booking.status=='completed').first())
    if not stayed:
        flash('Sirf stay karne ke baad review de sakte hain!', 'danger')
        return redirect(url_for('hotel_detail', hotel_id=hotel_id))
    if Review.query.filter_by(user_id=session['user_id'], hotel_id=hotel_id).first():
        flash('Aap pehle hi review de chuke hain!', 'warning')
        return redirect(url_for('hotel_detail', hotel_id=hotel_id))
    review = Review(user_id=session['user_id'], hotel_id=hotel_id, booking_id=stayed.id,
                    rating=request.form.get('rating', type=int),
                    comment=request.form.get('comment',''), is_verified_stay=True)
    db.session.add(review)
    hotel  = Hotel.query.get(hotel_id)
    all_r  = Review.query.filter_by(hotel_id=hotel_id).all()
    hotel.rating        = round(sum(r.rating for r in all_r)/len(all_r), 1)
    hotel.total_reviews = len(all_r)
    db.session.commit()
    flash('Review add ho gayi! ⭐', 'success')
    return redirect(url_for('hotel_detail', hotel_id=hotel_id))

# ══════════════════════════════════════════════
#  SUPPORT
# ══════════════════════════════════════════════

@app.route('/support', methods=['GET', 'POST'])
@login_required
def support():
    if request.method == 'POST':
        booking_id = request.form.get('booking_id') or None
        ticket = SupportTicket(user_id=session['user_id'], booking_id=booking_id,
                               subject=request.form['subject'], message=request.form['message'],
                               priority='urgent' if booking_id else 'normal')
        db.session.add(ticket)
        db.session.commit()
        flash(f'Ticket #{ticket.id} create ho gaya! 2 ghante mein reply. 🙏', 'success')
        return redirect(url_for('support'))
    my_tickets       = SupportTicket.query.filter_by(user_id=session['user_id']).order_by(SupportTicket.created_at.desc()).all()
    my_bookings_list = Booking.query.filter_by(user_id=session['user_id'], status='confirmed').all()
    return render_template('support.html', tickets=my_tickets, my_bookings=my_bookings_list)

# ══════════════════════════════════════════════
#  OWNER DASHBOARD + ANALYTICS
# ══════════════════════════════════════════════

@app.route('/owner/dashboard')
@login_required
@owner_required
def owner_dashboard():
    my_hotels  = Hotel.query.filter_by(owner_id=session['user_id']).all()
    hotel_ids  = [h.id for h in my_hotels]
    this_month = date.today().replace(day=1)
    all_b      = (Booking.query.join(Room)
                  .filter(Room.hotel_id.in_(hotel_ids), Booking.status=='confirmed').all())
    monthly_b  = [b for b in all_b if b.created_at.date() >= this_month]
    revenue    = sum(b.hotel_payout or 0 for b in monthly_b)
    total_rev  = sum(b.hotel_payout or 0 for b in all_b)

    # Analytics — monthly revenue
    monthly_data = {}
    for b in all_b:
        key = b.created_at.strftime('%b %Y')
        monthly_data[key] = round(monthly_data.get(key, 0) + (b.hotel_payout or 0), 0)

    # Category breakdown
    cat_data = {}
    for h in my_hotels:
        cat_data[h.category or 'other'] = cat_data.get(h.category or 'other', 0) + 1

    payouts = (Payout.query.filter(Payout.hotel_id.in_(hotel_ids), Payout.status=='scheduled')
               .order_by(Payout.due_date).limit(5).all())
    recent  = (Booking.query.join(Room).filter(Room.hotel_id.in_(hotel_ids))
               .order_by(Booking.created_at.desc()).limit(10).all())

    return render_template('owner_dashboard.html',
                           hotels=my_hotels, revenue=revenue, total_rev=total_rev,
                           total_bookings=len(monthly_b), all_bookings_count=len(all_b),
                           payouts=payouts, recent_bookings=recent,
                           monthly_data=json.dumps(monthly_data),
                           cat_data=json.dumps(cat_data))

@app.route('/owner/add-hotel', methods=['GET', 'POST'])
@login_required
@owner_required
def add_hotel():
    if request.method == 'POST':
        amenities = request.form.getlist('amenities')
        hotel = Hotel(
            owner_id=session['user_id'], name=request.form['name'],
            city=request.form['city'], state=request.form['state'],
            address=request.form['address'], description=request.form['description'],
            price_per_night=float(request.form['price']),
            category=request.form['category'], amenities=','.join(amenities),
            cancellation_policy=request.form['cancellation_policy'],
            latitude=float(request.form.get('latitude') or 0),
            longitude=float(request.form.get('longitude') or 0),
            commission_rate=10.0, is_available=True)
        db.session.add(hotel)
        db.session.flush()
        db.session.add(Room(hotel_id=hotel.id, room_type='standard',
                            capacity=2, price_per_night=hotel.price_per_night))
        db.session.commit()
        flash('Hotel listed! Commission sirf 10%. 🌿', 'success')
        return redirect(url_for('owner_dashboard'))
    return render_template('add_hotel.html')

# ══════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════

@app.route('/api/price-preview')
def api_price_preview():
    try:
        room_id   = int(request.args.get('room_id'))
        check_in  = datetime.strptime(request.args.get('check_in'),  '%Y-%m-%d').date()
        check_out = datetime.strptime(request.args.get('check_out'), '%Y-%m-%d').date()
        nights    = (check_out - check_in).days
        if nights <= 0: return jsonify({'error': 'Invalid dates'}), 400
        room  = Room.query.get_or_404(room_id)
        data  = calculate_pricing(room.price_per_night, nights, room.hotel.commission_rate)
        data['nights'] = nights
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/check-availability')
def api_availability():
    room_id   = int(request.args.get('room_id'))
    check_in  = datetime.strptime(request.args.get('check_in'),  '%Y-%m-%d').date()
    check_out = datetime.strptime(request.args.get('check_out'), '%Y-%m-%d').date()
    conflict  = Booking.query.filter(
        Booking.room_id==room_id, Booking.status.in_(['pending','confirmed']),
        Booking.check_in<check_out, Booking.check_out>check_in).first()
    return jsonify({'available': not bool(conflict)})

# ══════════════════════════════════════════════
#  SEED + RUN
# ══════════════════════════════════════════════

def seed():
    if Hotel.query.first(): return
    owner = User(name='Ramesh Verma', email='owner@demo.com', phone='9876543210', role='hotel_owner',
                 password=bcrypt.generate_password_hash('demo123').decode('utf-8'))
    cust  = User(name='Priya Sharma', email='customer@demo.com', phone='9123456789', role='customer',
                 password=bcrypt.generate_password_hash('demo123').decode('utf-8'))
    db.session.add_all([owner, cust])
    db.session.flush()
    hotels_data = [
        dict(name='Ayurveda Palace Jaipur', city='Jaipur', state='Rajasthan',
             price_per_night=2800, rating=4.8, total_reviews=312, category='luxury',
             amenities='pool,wifi,ac,gym,spa,parking', cancellation_policy='moderate',
             is_verified=True, last_verified_date=date.today()-timedelta(days=5),
             latitude=26.9124, longitude=75.7873),
        dict(name='Budget Wellness Inn Delhi', city='Delhi', state='Delhi NCR',
             price_per_night=899, rating=4.2, total_reviews=891, category='budget',
             amenities='wifi,ac,tv', cancellation_policy='flexible',
             is_verified=True, last_verified_date=date.today()-timedelta(days=2),
             latitude=28.6139, longitude=77.2090),
        dict(name='Sea Breeze Ayurveda Resort', city='Goa', state='Goa',
             price_per_night=4500, rating=4.9, total_reviews=567, category='resort',
             amenities='pool,wifi,ac,gym,beach,spa,restaurant', cancellation_policy='strict',
             is_verified=True, last_verified_date=date.today()-timedelta(days=1),
             latitude=15.2993, longitude=74.1240),
        dict(name='Himalayan Herb Retreat', city='Manali', state='Himachal Pradesh',
             price_per_night=1800, rating=4.5, total_reviews=234, category='budget',
             amenities='wifi,heater,parking', cancellation_policy='flexible',
             is_verified=False, latitude=32.2432, longitude=77.1892),
        dict(name='Heritage Ayurveda Palace', city='Udaipur', state='Rajasthan',
             price_per_night=5500, rating=4.7, total_reviews=445, category='luxury',
             amenities='pool,wifi,ac,spa,lake_view,restaurant', cancellation_policy='moderate',
             is_verified=True, last_verified_date=date.today()-timedelta(days=10),
             latitude=24.5854, longitude=73.7125),
        dict(name='City Wellness Hostel Mumbai', city='Mumbai', state='Maharashtra',
             price_per_night=650, rating=4.0, total_reviews=1203, category='hostel',
             amenities='wifi,locker,common_kitchen', cancellation_policy='flexible',
             is_verified=True, last_verified_date=date.today()-timedelta(days=3),
             latitude=19.0760, longitude=72.8777),
    ]
    for hd in hotels_data:
        h = Hotel(owner_id=owner.id, commission_rate=10.0, is_available=True,
                  description='Ayurvedic wellness experience in the heart of India.', **hd)
        db.session.add(h)
        db.session.flush()
        db.session.add(Room(hotel_id=h.id, room_type='deluxe', capacity=2, price_per_night=h.price_per_night))
    db.session.commit()
    print('✅ Ayurveda Bhavan ready!')
    print('   owner@demo.com / demo123')
    print('   customer@demo.com / demo123')

# Render ke liye — Gunicorn ke saath bhi DB create ho
with app.app_context():
    db.create_all()
    seed()
    app.run(debug=True, port=5000)
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed()
    app.run(debug=True, port=5000)
