import sqlite3
from comp_OSIT_filt import *


def initialize_db():
    try:
        sqliteConnection = sqlite3.connect('database.db')
        sqliteConnection.execute('CREATE TABLE IF NOT EXISTS coloc_files(meanr_ave VARCHAR, tsg_product VARCHAR NOT '
                                 'NULL, dataset VARCHAR NOT NULL, orbit_type VARCHAR NOT NULL, transects VARCHAR NOT '
                                 'NULL, limdate_in VARCHAR NOT NULL, limdate_out VARCHAR NOT NULL, user VARCHAR, '
                                 'min_length FLOAT NOT NULL, progress_recorder BOOLEAN NOT NULL, result VARCHAR);')
    except sqlite3.Error as error:
        print("Failed to insert multiple records into sqlite table", error)
    finally:
        if sqliteConnection:
            sqliteConnection.close()


def read_sqlite_table(sqlite_select_query):
    rows = []
    try:
        sqliteConnection = sqlite3.connect('database.db')
        cursor = sqliteConnection.cursor()
        cursor.execute(sqlite_select_query)
        records = cursor.fetchall()
        print("Total rows are:  ", len(records), "\n\n")
        for row in records:
            rows.append(row[0])
        cursor.close()

    except sqlite3.Error as error:
        print("Failed to read data from sqlite table", error)
    finally:
        if sqliteConnection:
            sqliteConnection.close()
    return rows


def add_coloc_db(coloc_info):
    try:
        sqliteConnection = sqlite3.connect('database.db')
        cursor = sqliteConnection.cursor()
        cursor.execute('INSERT OR IGNORE INTO coloc_files (meanr_ave , tsg_product, dataset, orbit_type, transects, '
                       'limdate_in, limdate_out, min_length) VALUES ("{}","{}", "{}","{}","{}","{}","{}",'
                       '"{}");'.format(coloc_info['Type de moyenne'], coloc_info['Produit TSG'], coloc_info['Produit '
                                                                                                            'SMOS'],
                                       coloc_info["Type d'orbite"], coloc_info['Transects'], coloc_info['Date min'],
                                       coloc_info['Date max'], coloc_info['Longueur minimale']))
        if len(cursor) == 0:
            path = cursor.execute('SELECT result FROM coloc_types WHERE meanr_ave = "{}" AND tsg_product = "{}" AND '
                                  'tsg_product = "{}" AND tsg_product = "{}" AND tsg_product = "{}" AND tsg_product = '
                                  '"{}" AND tsg_product = "{}" AND tsg_product = "{}"; '
                                  .format(coloc_info['Type de moyenne'], coloc_info['Produit TSG'],
                                          coloc_info['Produit SMOS'],coloc_info["Type d'orbite"],
                                          coloc_info['Transects'], coloc_info['Date min'], coloc_info['Date max'],
                                          coloc_info['Longueur minimale']))
            cursor.close()
            return path
        else:
            pass
            # do the coloc
        cursor.close()
    except sqlite3.Error as error:
        print("Failed to read data from sqlite table", error)
    finally:
        if sqliteConnection:
            sqliteConnection.close()
