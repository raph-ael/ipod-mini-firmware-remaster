/* Write an iTunesDB from a track list on stdin, using libgpod.
 *
 * usage: kidsdb <mountpoint>
 *
 * Each input line has tab-separated fields:
 *   ipod_path title artist album genre track_nr tracks length_ms bitrate
 *   samplerate size audiobook playlist
 *
 * An existing database is reused, so bookmarks survive. libgpod merges the
 * iPod's "Play Counts" file on parse and removes it on write.
 */
#include <gpod/itdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { F_PATH, F_TITLE, F_ARTIST, F_ALBUM, F_GENRE, F_TRACK_NR, F_TRACKS, F_LENGTH,
       F_BITRATE, F_SAMPLERATE, F_SIZE, F_AUDIOBOOK, F_PLAYLIST, F_COUNT };

static Itdb_iTunesDB *open_db(const char *mount)
{
    GError *error = NULL;
    gchar *path = itdb_get_itunesdb_path(mount);
    Itdb_iTunesDB *itdb = NULL;

    if (path) {
        itdb = itdb_parse(mount, &error);
        g_free(path);
        if (!itdb) {
            fprintf(stderr, "cannot parse database: %s\n", error->message);
            exit(1);
        }
        return itdb;
    }

    itdb = itdb_new();
    itdb_set_mountpoint(itdb, mount);
    Itdb_Playlist *mpl = itdb_playlist_new("iPod", FALSE);
    itdb_playlist_set_mpl(mpl);
    itdb_playlist_add(itdb, mpl, -1);
    return itdb;
}

static void drop_user_playlists(Itdb_iTunesDB *itdb)
{
    GList *copy = g_list_copy(itdb->playlists);
    for (GList *l = copy; l; l = l->next) {
        Itdb_Playlist *pl = l->data;
        if (!itdb_playlist_is_mpl(pl))
            itdb_playlist_remove(pl);
    }
    g_list_free(copy);
}

static Itdb_Playlist *playlist_named(Itdb_iTunesDB *itdb, const char *name)
{
    Itdb_Playlist *pl = itdb_playlist_by_name(itdb, (gchar *)name);
    if (!pl) {
        pl = itdb_playlist_new(name, FALSE);
        itdb_playlist_add(itdb, pl, -1);
    }
    return pl;
}

static void replace(gchar **field, const char *value)
{
    g_free(*field);
    *field = *value ? g_strdup(value) : NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <mountpoint>\n", argv[0]);
        return 2;
    }

    Itdb_iTunesDB *itdb = open_db(argv[1]);
    Itdb_Playlist *mpl = itdb_playlist_mpl(itdb);
    drop_user_playlists(itdb);

    GHashTable *known = g_hash_table_new(g_str_hash, g_str_equal);
    for (GList *l = itdb->tracks; l; l = l->next) {
        Itdb_Track *t = l->data;
        g_hash_table_insert(known, t->ipod_path, t);
    }

    GHashTable *wanted = g_hash_table_new(g_direct_hash, g_direct_equal);
    char line[2048];
    unsigned added = 0, kept = 0;

    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\n")] = 0;
        gchar **f = g_strsplit(line, "\t", -1);
        if (g_strv_length(f) != F_COUNT) {
            fprintf(stderr, "bad input line: %s\n", line);
            return 1;
        }

        Itdb_Track *t = g_hash_table_lookup(known, f[F_PATH]);
        if (t) {
            kept++;
        } else {
            t = itdb_track_new();
            t->ipod_path = g_strdup(f[F_PATH]);
            t->filetype = g_strdup("MPEG audio file");
            t->transferred = TRUE;
            t->time_added = time(NULL);
            itdb_track_add(itdb, t, -1);
            itdb_playlist_add_track(mpl, t, -1);
            added++;
        }

        replace(&t->title, f[F_TITLE]);
        replace(&t->artist, f[F_ARTIST]);
        replace(&t->album, f[F_ALBUM]);
        replace(&t->genre, f[F_GENRE]);
        t->track_nr = atoi(f[F_TRACK_NR]);
        t->tracks = atoi(f[F_TRACKS]);
        t->tracklen = atoi(f[F_LENGTH]);
        t->bitrate = atoi(f[F_BITRATE]);
        t->samplerate = atoi(f[F_SAMPLERATE]);
        t->size = strtoul(f[F_SIZE], NULL, 10);
        t->remember_playback_position = atoi(f[F_AUDIOBOOK]) ? 1 : 0;
        t->skip_when_shuffling = t->remember_playback_position;
        g_hash_table_add(wanted, t);

        if (*f[F_PLAYLIST])
            itdb_playlist_add_track(playlist_named(itdb, f[F_PLAYLIST]), t, -1);
        g_strfreev(f);
    }

    GList *copy = g_list_copy(itdb->tracks);
    unsigned removed = 0;
    for (GList *l = copy; l; l = l->next) {
        Itdb_Track *t = l->data;
        if (!g_hash_table_contains(wanted, t)) {
            itdb_playlist_remove_track(mpl, t);
            itdb_track_remove(t);
            removed++;
        }
    }
    g_list_free(copy);

    GError *error = NULL;
    if (!itdb_write(itdb, &error)) {
        fprintf(stderr, "cannot write database: %s\n", error->message);
        return 1;
    }
    printf("%u new, %u kept, %u removed, %u tracks in %u playlists\n", added, kept, removed,
           itdb_tracks_number(itdb), itdb_playlists_number(itdb) - 1);
    itdb_free(itdb);
    return 0;
}
