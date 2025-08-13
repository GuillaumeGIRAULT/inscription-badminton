from flask import Flask, request, redirect, url_for, render_template_string, session, flash, Response
import sqlite3
import os
import csv
import io

app = Flask(__name__)
app.secret_key = 'vraimentsecret'  # Nécessaire pour la session
DB_FILE = 'inscriptions.db'
ADMIN_PASSWORD = 'admin123'
MAX_PLACES = 50

# Création auto de la table si besoin
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Check if 'laboratoire' column exists
    c.execute("PRAGMA table_info(inscriptions)")
    columns = [col[1] for col in c.fetchall()]
    if 'laboratoire' not in columns:
        # If table does not exist, create it with laboratoire column
        c.execute('''
            CREATE TABLE IF NOT EXISTS inscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                email TEXT NOT NULL,
                laboratoire TEXT,
                accompagnants INTEGER,
                commentaire TEXT
            )
        ''')
        conn.commit()
        # If table existed before without laboratoire column, add it
        if 'laboratoire' not in columns:
            try:
                c.execute('ALTER TABLE inscriptions ADD COLUMN laboratoire TEXT')
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists or table just created
                pass
    else:
        # Table exists and has laboratoire column, ensure table exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS inscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                email TEXT NOT NULL,
                laboratoire TEXT,
                accompagnants INTEGER,
                commentaire TEXT
            )
        ''')
        conn.commit()
    conn.close()

init_db()

# Calcul des places utilisées/restantes
def get_places_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # total = nombre d'inscrits + somme des accompagnants
    c.execute('SELECT COUNT(*), COALESCE(SUM(accompagnants), 0) FROM inscriptions')
    count_inscrits, sum_accomp = c.fetchone()
    conn.close()
    total = (count_inscrits or 0) + (sum_accomp or 0)
    restantes = MAX_PLACES - total
    if restantes < 0:
        restantes = 0
    return total, restantes

FORM_HTML = """
<!doctype html>
<title>Inscription</title>
<h2>Formulaire d'inscription Badmington 28/09/2025</h2>
<p><strong>Lieu :</strong> Gymnase du lycée Val de Seine, 5–11 Avenue Georges Braque, 76120 Le Grand-Quevilly<br>
<strong>Date :</strong> Dimanche 28/09/2025 matin</p>
<img src="{{ url_for('static', filename='badmington.jpg') }}" alt="Badminton" style="max-width:300px; display:block; margin-bottom:15px;">
<p><strong>Places restantes : {{ places_restantes }}</strong></p>
{% if complet %}
<p style="color:red; font-weight:bold;">Complet – il n'y a plus de places disponibles.</p>
{% endif %}
<form method="post">
    <label>Nom: <input type="text" name="nom" required></label><br>
    <label>Prénom: <input type="text" name="prenom" required></label><br>
    <label>Email: <input type="email" name="email" required></label><br>
    <label>Laboratoire: 
        <select name="laboratoire" required>
            <option value="Ma1">Ma1</option>
            <option value="Ma2">Ma2</option>
            <option value="Bo">Bo</option>
            <option value="ÇA">ÇA</option>
            <option value="IS">IS</option>
            <option value="DE">DE</option>
            <option value="BS">BS</option>
            <option value="YS">YS</option>
            <option value="CL">CL</option>
            <option value="DA">DA</option>
            <option value="ME">ME</option>
            <option value="SH">SH</option>
            <option value="AM">AM</option>
            <option value="EU">EU</option>
            <option value="SS">SS</option>
            <option value="FL">FL</option>
            <option value="QG">QG</option>
        </select>
    </label><br>
    <label>Nombre d'accompagnants (optionnel, priorité aux salariés): <input type="number" name="accompagnants" min="0" value="0" max="{{ max_accomp }}"></label><br>
    <label>Commentaire: <textarea name="commentaire"></textarea></label><br>
    <button type="submit" {% if complet %}disabled{% endif %}>S'inscrire</button>
</form>
<br>
<img src="{{ url_for('static', filename='plan.png') }}" alt="Plan" style="max-width:400px; display:block; margin-top:15px;">
<img src="{{ url_for('static', filename='acces.png') }}" alt="Accès" style="max-width:400px; display:block; margin-top:15px;">
"""

CONFIRM_HTML = """
<!doctype html>
<title>Confirmation</title>
<h2>Merci pour votre inscription !</h2>
{% if accomp_initial is not none and accomp_enregistre is not none and accomp_enregistre < accomp_initial %}
<p>Note : vous aviez demandé {{ accomp_initial }} accompagnant(s), mais seulement {{ accomp_enregistre }} a/ont été enregistré(s) en fonction des places restantes (priorité aux salariés).</p>
{% endif %}
<p><a href="{{ url_for('inscription') }}">Retour au formulaire</a></p>
"""

LOGIN_HTML = """
<!doctype html>
<title>Connexion admin</title>
<h2>Connexion administrateur</h2>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul style="color:red;">
    {% for msg in messages %}
      <li>{{ msg }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<form method="post">
    <label>Mot de passe: <input type="password" name="password" required></label>
    <button type="submit">Se connecter</button>
</form>
"""

LISTE_HTML = """
<!doctype html>
<title>Liste des inscrits</title>
<h2>Liste des inscrits</h2>
<p><strong>Capacité : {{ max_places }} — Inscrits (avec accompagnants) : {{ total_places }} — Restantes : {{ places_restantes }}</strong></p>
<table border="1" cellpadding="5">
    <tr>
        <th>ID</th>
        <th>Nom</th>
        <th>Prénom</th>
        <th>Email</th>
        <th>Laboratoire</th>
        <th>Accompagnants</th>
        <th>Commentaire</th>
    </tr>
    {% for ins in inscriptions %}
    <tr>
        <td>{{ ins[0] }}</td>
        <td>{{ ins[1] }}</td>
        <td>{{ ins[2] }}</td>
        <td>{{ ins[3] }}</td>
        <td>{{ ins[4] }}</td>
        <td>{{ ins[5] }}</td>
        <td>{{ ins[6] }}</td>
    </tr>
    {% endfor %}
</table>
<p><a href="{{ url_for('logout') }}">Déconnexion</a>
<br><a href="{{ url_for('export_csv') }}">Exporter en CSV</a>
</p>
"""

@app.route('/', methods=['GET', 'POST'])
def inscription():
    total, places_restantes = get_places_stats()
    complet = places_restantes <= 0
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip()
        laboratoire = request.form.get('laboratoire', '').strip()
        # Champ accompagnants optionnel, priorité aux salariés : on ne dépasse pas la capacité
        accomp_str = request.form.get('accompagnants', '0')
        try:
            accomp_demandes = max(0, int(accomp_str))
        except ValueError:
            accomp_demandes = 0
        # Recalcule des places restantes pour éviter une course entre requêtes
        _, places_restantes = get_places_stats()
        if places_restantes <= 0:
            # Plus de place du tout
            return render_template_string(FORM_HTML, places_restantes=0, max_accomp=0, complet=True)
        # On garantit 1 place pour le salarié, les accompagnants sont limités au reste
        max_pour_accomp = max(0, places_restantes - 1)
        accompagnants = min(accomp_demandes, max_pour_accomp)
        commentaire = request.form.get('commentaire', '').strip()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO inscriptions (nom, prenom, email, laboratoire, accompagnants, commentaire) VALUES (?, ?, ?, ?, ?, ?)',
                  (nom, prenom, email, laboratoire, accompagnants, commentaire))
        conn.commit()
        conn.close()
        return render_template_string(CONFIRM_HTML, accomp_initial=accomp_demandes, accomp_enregistre=accompagnants)
    # GET : afficher formulaire avec places restantes et limite dynamique pour accompagnants
    total, places_restantes = get_places_stats()
    complet = places_restantes <= 0
    max_accomp = max(0, places_restantes - 1)
    return render_template_string(FORM_HTML, places_restantes=places_restantes, max_accomp=max_accomp, complet=complet)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin' in session and session['admin']:
        return redirect(url_for('liste'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('liste'))
        else:
            flash('Mot de passe incorrect.')
    return render_template_string(LOGIN_HTML)

@app.route('/liste')
def liste():
    if 'admin' not in session or not session['admin']:
        return redirect(url_for('admin'))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, nom, prenom, email, laboratoire, accompagnants, commentaire FROM inscriptions ORDER BY id DESC')
    inscriptions = c.fetchall()
    conn.close()
    total_places_utilisees, places_restantes = get_places_stats()
    return render_template_string(LISTE_HTML, inscriptions=inscriptions, max_places=MAX_PLACES, total_places=total_places_utilisees, places_restantes=places_restantes)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin'))


# Route pour exporter les inscriptions en CSV (admin seulement)
@app.route('/export_csv')
def export_csv():
    if 'admin' not in session or not session['admin']:
        return redirect(url_for('admin'))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, nom, prenom, email, laboratoire, accompagnants, commentaire FROM inscriptions ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'nom', 'prenom', 'email', 'laboratoire', 'accompagnants', 'commentaire'])
    for row in rows:
        writer.writerow(row)
    csv_str = output.getvalue()
    output.close()
    response = Response(csv_str, mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=inscriptions.csv'
    return response

if __name__ == '__main__':
    app.run(debug=True)