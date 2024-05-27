import os

from flask import Flask, session, redirect, url_for, request, render_template, flash, get_flashed_messages

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from collections import Counter
from datetime import datetime, timedelta


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_PERMANENT'] = timedelta(minutes=5)


client_id = 'fa7d7e379e7f42ca859cea494351fcc5'
client_secret = '614d81cfdc344adfb4787bff30a8e98e'
redirect_uri = 'https://selekta.onrender.com/callback'
scope = 'playlist-read-private playlist-read-collaborative user-top-read user-read-recently-played user-read-currently-playing playlist-modify-public playlist-modify-private'

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)
sp = Spotify(auth_manager=sp_oauth)

def get_top_genres():
    # Fetch the user's top artists
    top_artists = sp.current_user_top_artists()

    # Extract the genres from the top artists
    genres = [genre for artist in top_artists['items'] for genre in artist['genres']]

    # Count the occurrences of each genre
    genre_counts = Counter(genres)

    return genre_counts.most_common()

@app.route('/authenticated')
def authenticated():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
        
    user = sp.current_user()

    recently_played_tracks = sp.current_user_recently_played()
    currently_playing_track = sp.current_user_playing_track()

    playlists = sp.current_user_playlists()

    genres = get_top_genres()[:5]

    return render_template('authenticated.html', user=user, recently_played_tracks=recently_played_tracks, currently_playing_track=currently_playing_track,  playlists_info=playlists, genres=[genre for genre, count in genres], counts=[count for genre, count in genres])

@app.route('/')
def landing_page():
    # Check if the user is logged in
    if 'user' in session:
        # If the user is logged in, redirect them to the authenticated page
        return redirect(url_for('authenticated'))
    else:
        # If the user is not logged in, render the landing page
        return render_template('landing_page.html')
    
@app.route('/login')
def login():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    else:
        return redirect(url_for('authenticated'))

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('authenticated'))

@app.route('/get_top_tracks')
def get_top_tracks():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    user = sp.current_user()

    time_range = request.args.get('time_range', 'medium_term')

    tracks = sp.current_user_top_tracks(limit=50, time_range=time_range)

    messages = get_flashed_messages()

    return render_template('get_top_tracks.html', user=user, tracks=tracks, time_range=time_range, messages=messages)

@app.route('/get_top_artists')
def get_top_artists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    user = sp.current_user()

    time_range = request.args.get('time_range', 'medium_term')

    artists = sp.current_user_top_artists(limit=50, time_range=time_range)

    return render_template('get_top_artists.html', user=user, artists=artists, time_range=time_range)


@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    user = sp.current_user()
    user_id = user['id']  # Get the user's Spotify ID

    time_range = request.form.get('time_range', 'medium_term')

    tracks = sp.current_user_top_tracks(limit=50, time_range=time_range)

    # Get the track IDs
    track_ids = [track['id'] for track in tracks['items']]

    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Create a new playlist for the user with the current date and time range in the name
    playlist_name = f"Top Tracks Playlist ({time_range}, {current_date})"
    playlist = sp.user_playlist_create(user_id, playlist_name)

    # Add the top tracks to the new playlist
    sp.playlist_add_items(playlist['id'], track_ids)

    flash("Playlist created successfully")
    return redirect(url_for('get_top_tracks', time_range=time_range))

@app.route('/create_recommended_playlist', methods=['POST'])
def create_recommended_playlist():
    # Get the time range selected by the user
    time_range = request.form.get('time_range', 'medium_term')

    # Get the user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=5, time_range=time_range)['items']
    seed_tracks = [track['id'] for track in top_tracks]

    # Get recommendations based on the user's top tracks
    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=30)['tracks']
    recommendation_ids = [track['id'] for track in recommendations]

    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Create a new playlist and add the recommended tracks to it
    user = sp.current_user()
    playlist_name = f"Recommended Tracks ({time_range}, {current_date})"
    playlist = sp.user_playlist_create(user['id'], playlist_name)
    sp.playlist_add_items(playlist['id'], recommendation_ids)

    flash("Recommended playlist created successfully")
    return redirect(url_for('get_top_tracks', time_range=time_range))

@app.route('/create_playlist_based_on_button', methods=['GET', 'POST'])
def create_playlist_based_on_button():
    if request.method == 'POST':
        button_pressed = request.form.get('button')  # assuming the button name is 'button'

        if button_pressed:
            # Get the time range from the button pressed
            time_range = '_'.join(button_pressed.split('_')[:2])

            # Get the user's top tracks or artists based on the button pressed
            if button_pressed in ['short_term_tracks', 'medium_term_tracks', 'long_term_tracks']:
                items = sp.current_user_top_tracks(limit=5, time_range=time_range)['items']
                seed_type = 'tracks'
            elif button_pressed in ['short_term_artists', 'medium_term_artists', 'long_term_artists']:
                items = sp.current_user_top_artists(limit=5, time_range=time_range)['items']
                seed_type = 'artists'
            else:
                return "Invalid button pressed", 400

            # Get the IDs of the top tracks or artists
            seed_ids = [item['id'] for item in items]

            # Get recommendations based on the top tracks or artists
            if seed_type == 'tracks':
                recommendations = sp.recommendations(seed_tracks=seed_ids, limit=30)['tracks']
            else:
                recommendations = sp.recommendations(seed_artists=seed_ids, limit=30)['tracks']

        else:
            # New code for creating a playlist based on the artist names
            artist_names = [request.form.get(f'artist{i}') for i in range(1, 6) if request.form.get(f'artist{i}')]

            # Search for each artist and get their ID
            seed_ids = []
            for name in artist_names:
                results = sp.search(q='artist:' + name, type='artist')
                if results['artists']['items']:
                    seed_ids.append(results['artists']['items'][0]['id'])

            # Get recommendations based on the artists
            recommendations = sp.recommendations(seed_artists=seed_ids, limit=30)['tracks']

        recommendation_ids = [track['id'] for track in recommendations]

        # Get the current date
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Create a new playlist and add the recommended tracks to it
        user = sp.current_user()
        playlist_name = f"Recommended Tracks ({button_pressed if button_pressed else 'User Artists'}, {current_date})"
        playlist = sp.user_playlist_create(user['id'], playlist_name)

        # Only try to add tracks to the playlist if there are any recommendations
        if recommendation_ids:
            sp.playlist_add_items(playlist['id'], recommendation_ids)
            flash("Recommended playlist created successfully")
        else:
            flash("No recommendations found for the selected tracks or artists")

        return render_template('playlist_creator.html')
    else:
        # If it's a GET request, just render the template
        return render_template('playlist_creator.html')
    
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return redirect(url_for('landing_page'))
    else:
        return '''
            <form method="POST">
                <input type="submit" value="Logout">
            </form>
        '''

if __name__ == "__main__":
    app.run(debug=True)