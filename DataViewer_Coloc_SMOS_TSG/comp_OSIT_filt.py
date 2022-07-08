from scipy.io import loadmat
import numpy as np
from datetime import datetime, timedelta
import h5py
import xarray as xr
import pandas as pd
from math import floor
from scipy import logical_and, spatial

from web.models import Dataset, TSGTransect, SatelliteTransect


def matlab_date_to_datetime(datev):
    return pd.NaT if np.isnan(datev) \
        else datetime.fromordinal(int(datev)) + timedelta(days=datev % 1) - timedelta(days=366)


def datevec(d):
    """datetime d to vector (d.year, d.month, d.day, d.hour, d.minute, d.second)"""
    def datetime2vector(d):
        return [d.year, d.month, d.day, d.hour, d.minute, d.second]

    if isinstance(d, float):
        d = np.array([d])
    return np.array([datetime2vector(matlab_date_to_datetime(x)) for x in d])


def great_circle(pt1, pt2):
    """Great circle distance between (lon1, lat1) and (lon2, lat2)"""
    a = np.deg2rad(pt1[:, 0])
    b = np.deg2rad(pt2[:, 0])
    C = np.deg2rad(pt2[:, 1] - pt1[:, 1])

    dist = np.arccos(np.multiply(np.sin(b), np.sin(a)) + np.multiply(np.multiply(np.cos(b), np.cos(a)), np.cos(C)))

    return np.rad2deg(dist)[:, np.newaxis]


class ColocalizationProcess(object):
    """Processus of colocalization"""
    transect_dir = 'LSAT-DATA/transects/{}'
    dataset_dir = 'LSAT-DATA/datasets/{}'
    leg_SMOS = 0
    delta_near = 5
    ngrid_coloc = 0

    # Premier mois de données SMOS
    moisoriSSS = np.array([2010, 7, 1])

    def __init__(self, meanr_ave, tsg_product, dataset, orbit_type, transects, limdate_in, limdate_out, user,
                 min_length, progress_recorder):
        self.meanr_ave = meanr_ave
        self.tsg_product = tsg_product
        self.dataset = dataset
        self.transect_file = self.transect_dir.format(tsg_product.file)
        self.dataset_file = self.dataset_dir.format(Dataset.name_(dataset.name))
        self.transects = transects
        self.limdate_in = limdate_in
        self.limdate_out = limdate_out
        self.min_length = min_length
        self.orbit_type = orbit_type
        self.progress_recorder = progress_recorder
        self.user = user

        if meanr_ave == 25:
            self.dnearc = 0.125  # maximum distance (degree) from TSG's mesure to keep a satellite data
            self.tmeanc = 0.125  # temps max difference (part of day) for mean-averaging TSG's mesures
            self.dmeanc = 0.25  # distance max difference (degree) for mean-averaging TSG's mesures
            self.str_dmeanc = '25'  # distance max difference (degree) for mean-averaging TSG's mesures
        elif meanr_ave == 50:
            self.dnearc = 0.125  # maximum distance (degree) from TSG's mesure to keep a satellite data
            self.tmeanc = 0.125  # temps max difference (part of day) for mean-averaging TSG's mesures
            self.dmeanc = 0.5  # distance max difference (degree) for mean-averaging TSG's mesures
            self.str_dmeanc = '50'  # distance max difference (degree) for mean-averaging TSG's mesures

        else:  # meanr_ave == 75
            self.dnearc = 0.75  # maximum distance (degree) from TSG's mesure to keep a satellite data
            self.tmeanc = 0.5  # temps max difference (part of day) for mean-averaging TSG's mesures
            self.dmeanc = 0.75  # distance max difference (degree) for mean-averaging TSG's mesures
            self.str_dmeanc = '75'  # distance max difference (degree) for mean-averaging TSG's mesures

        print('''Dataset: {}
        Transect file: {}
        Products: {}
        w/ mean radius: {} and min(nb measures TSG): {}'''.format(
            self.dataset, self.transect_file, self.orbit_type, self.str_dmeanc, self.min_length))

    def process(self):
        mat = loadmat(self.dataset_file)
        SSS_smos3 = mat['SSS']
        d3_long = mat['SSS'].shape[-1]
        print('Input 3 : {}, {}; {} samples'.format(self.leg_SMOS, self.dataset_file, d3_long))
        dateSSS3 = np.squeeze(mat['ttdayJulian'])
        SSS_smos3[SSS_smos3 == 0] = np.nan

        print('time frame: {}---{}'.format(self.limdate_in, self.limdate_out))

        # Read transect file
        if self.transect_file.endswith('.mat'):
            with h5py.File(self.transect_file, 'r') as tf:
                transectTSG = np.array(tf['transectTSG']).T
        elif self.transect_file.endswith('.nc'):
            ds = xr.open_dataset(self.transect_file)
            transectTSG = ds['transectTSG'].values
            ds.close()
        else:
            print('*** Unknown transect file format! {}'.format(self.transect_file))
            raise

        print('TransectTSG: {} is loaded'.format(self.transect_file))
        nbtransect = transectTSG.shape[0]
        txt_date = np.tile('____________________________________________________', nbtransect)
        for itransect in self.transects:
            nonan = ~np.isnan(transectTSG[itransect, :, 0])
            fnonan = np.nonzero(nonan == 1)
            jourref = transectTSG[itransect, fnonan[0][0], 0]
            jourmesure = transectTSG[itransect, fnonan[0][-1], 0]
            txt_date[itransect] = '{} -- {}'.format(matlab_date_to_datetime(jourref),
                                                    matlab_date_to_datetime(jourmesure))

        print('Data ok: {}'.format(datetime.now()))

        for i, itransect in enumerate(self.transects):

            full_mth = datevec(transectTSG[itransect, :, 0])
            date_ok = np.arange(0, len(full_mth[:, 1]))[:, np.newaxis]
            unTSG = np.empty((np.sum(~np.isnan(transectTSG[itransect, date_ok, 0])), 1))
            unTSG[:] = np.nan
            unTSG = transectTSG[itransect, range(len(unTSG)), :]
            un2TSG = np.empty((unTSG.shape[0], 6))
            un2TSG[:] = np.nan

            transect_name = '** itransect = {}; Nb pts {}; dates: {}; {}-{} **'.format(
                itransect, unTSG.shape[0], txt_date[itransect], self.tsg_product, self.dataset)

            print(transect_name)

            isupmesure = -1
            latc_used = 0
            lonc_used = 0

            # Boucle sur le nombre de mesures du transect en cours
            for imesure in range(unTSG.shape[0]):
                latc = ((round((unTSG[imesure, 1] + 90) * 4)) / 4 - 90) - self.dnearc
                lonc = ((round((unTSG[imesure, 2] + 180) * 4)) / 4 - 180) - self.dnearc
                if latc_used != latc and lonc_used != lonc:
                    replatc = np.tile(latc, (unTSG.shape[0], 1))
                    replonc = np.tile(lonc, (unTSG.shape[0], 1))
                    repdate = np.tile(unTSG[imesure, 0], (unTSG.shape[0], 1))
                    if not unTSG[:, 1].shape == (1, ):
                        dist_center = great_circle(np.squeeze(np.dstack((unTSG[:, 1], unTSG[:, 2]))),
                                                   np.squeeze(np.dstack((replatc, replonc))))
                        time_center = np.abs(repdate - unTSG[:, 0][..., np.newaxis])
                        round_sal = np.nonzero(logical_and(dist_center < self.dmeanc, time_center < self.tmeanc))[0]
                        isupmesure += 1
                        un2TSG[isupmesure, 0] = unTSG[imesure, 0]
                        un2TSG[isupmesure, 1] = unTSG[imesure, 1]
                        un2TSG[isupmesure, 2] = unTSG[imesure, 2]
                        un2TSG[isupmesure, 3] = np.mean(unTSG[round_sal, 3])
                        un2TSG[isupmesure, 4] = np.mean(unTSG[round_sal, 4])
                        un2TSG[isupmesure, 5] = np.nanstd(unTSG[round_sal, 3])
                        latc_used = latc
                        lonc_used = lonc
                    else:
                        isupmesure += 1
                        un2TSG[isupmesure, :] = np.nan

            # Nouveau unTSG qui correspond maintenant aux seules mesures moyennées TSG
            unTSG = np.empty((np.sum(~np.isnan(un2TSG[:, 0])), 1))
            unTSG = un2TSG[range(unTSG.shape[0]), :]

            # Déclaration matrices SMOS et ISAS
            sal3 = np.squeeze(np.empty((1, unTSG.shape[0])))
            if unTSG.shape[0] <= 1:
                continue
            sal3[:] = np.nan

            for imesure in range(unTSG.shape[0]):
                # Boucle sur le nombre de mesures du transect en cours
                # Pour des localisations à 0.25°, sur la grille (1440,720)

                # 1. Déterminer les bandes pour lesquelles le point de grille pour SSSsmos est rempli
                #    travail sur la dateTSG (positions valides grille) et médiane med_SSS

                if unTSG[imesure, 1] == -90:
                    ilati = 720
                else:
                    ilati = floor((unTSG[imesure, 1] + 90) / 0.25)
                if unTSG[imesure, 2] == -180:
                    ilong = 1440
                else:
                    ilong = floor((unTSG[imesure, 2] + 180) / 0.25)

                # dk nbday for new dataset. Taking number 3 of v622
                if unTSG[imesure, 0] > dateSSS3[-1] + 2:
                    nbdaySSS3 = d3_long + 1
                elif unTSG[imesure, 0] < dateSSS3[0] - 2:
                    nbdaySSS3 = 0
                else:
                    nbdaySSS3 = spatial.KDTree(dateSSS3[:, np.newaxis]).query([unTSG[imesure, 0]])[1]

                # Détermination des domaines des indices lon/lat à couvrir
                indicelgbeg = ilong - self.ngrid_coloc
                indicelgend = ilong + self.ngrid_coloc
                rangelon = np.mod(
                    np.array([[indicelgbeg]]) if indicelgbeg == indicelgend
                    else np.arange(indicelgbeg, indicelgend)[:, np.newaxis], 1440)
                rangelon[np.nonzero(rangelon == 0)[0]] = 1440

                indiceltbeg = ilati - self.ngrid_coloc
                indiceltend = ilati + self.ngrid_coloc
                rangelat = np.mod(
                    np.array([[indiceltbeg]]) if indiceltbeg == indiceltend
                    else np.arange(indiceltbeg, indiceltend)[:, np.newaxis], 720)
                rangelat[np.nonzero(rangelat == 0)[0]] = 720

                # Calcul de la moyenne des salinités dans une boite ngrid_coloc × (+/-0.25°) par rapport au centre
                if nbdaySSS3 > 0 and nbdaySSS3 <= d3_long:
                    SSSz3 = SSS_smos3[rangelon - 1, rangelat - 1, nbdaySSS3]
                    sal3[imesure] = np.mean(SSSz3[~np.isnan(SSSz3)])
                else:
                    sal3[imesure] = np.nan

            tdict = dict((n, v.tolist()) for n, v in
                         zip(['fulldateTSG', 'fulllatTSG', 'fulllonTSG', 'fullsalTSG', 'fullerrTSG'], unTSG.T))

            tsg_transect = TSGTransect.objects.get(index=itransect, tsg_product=self.tsg_product)

            transect, created = SatelliteTransect.objects.update_or_create(
                dataset=self.dataset,
                tsg_transect=tsg_transect,
                defaults={'text_title': transect_name,
                          'description': '',
                          'salinities': np.squeeze(sal3).tolist(),
                          'tsg_longitudes': tdict['fulllonTSG'],
                          'tsg_latitudes': tdict['fulllatTSG'],
                          'tsg_dates': list(map(matlab_date_to_datetime, tdict['fulldateTSG'])),
                          'tsg_salinities': tdict['fullsalTSG'],
                          'tsg_std': tdict['fullerrTSG'],
                          'creator': self.user
                          }
            )

            self.progress_recorder.set_progress(i + 1, len(self.transects))
