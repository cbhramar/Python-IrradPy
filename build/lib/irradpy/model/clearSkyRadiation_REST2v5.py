import numpy as np
import os
import warnings
from ..extractor.extract import extract_dataset_list, extract_dataset, extract_for_MERRA2
from .solarGeometry import *
import pandas as pd

class ClearSkyREST2v5:

    def __init__(self, lat: np.ndarray, lon: np.ndarray, elev, time, datadir, pandas=True):
        if lat.shape != lon.shape:
            raise Exception('lat and lon not match...')
        if np.max(np.abs(lat)) > 90:
            raise Exception('90<= lattitude <=90, reset your latitude')
        if np.max(np.abs(lon)) > 180:
            raise Exception('-180<= lontitude <=180, reset your lontitude')

        station_num = np.size(lat)
        self.lat = lat.reshape([station_num, ])
        self.lon = lon.reshape([station_num, ])
        self.elev = elev.reshape([station_num, 1])
        self.time = time
        self.datadir = datadir
        self.pandas_output = pandas

    def clear_sky_REST2V5(self, zenith_angle: np.ndarray, Eext: np.ndarray, pressure: np.ndarray,
                         water_vapour: np.ndarray,
                         ozone: np.ndarray, nitrogen_dioxide: np.ndarray, AOD550: np.ndarray,
                         Angstrom_exponent: np.ndarray,
                         surface_albedo: np.ndarray):
        """
        Input requirements


        Expected input type is np.ndarry (though could work for single).
        zenith_angle        [radians]
        surface_albedo      [fraction]
        pressure            [mb]                (local barometric)
        Angstrom_exponent   [dimensionless]     (also known as alpha)
        AOD_550             [dimensionless]     (aerosol optical depth at 550 nm)
        ozone               [atm.cm]            (total columular amount)
        nitrogen_dioxide    [atm.cm]            (total columular amount)
        water_vapour        [atm.cm]            (total columular amount)
        Eext                [Wm-2]              (Extraterrestrial irradiance)


        Every Variable Need to be np.ndarry. np.matrix will cause fatal error

        This model is called the REST2v5 clear sky model, written and designed by
        Christian A. Gueymard over a series of publications, though primarily in
        his 2008 paper in the Journal of Solar Energy (volume 82, issue 3, pages
        272-285) titled "REST2: High-performance solar radiation model for
        cloudless-sky irradiance,  illuminance, and photosynthetically active
        radiation - Validation with a benchmark dataset"

        you can run this model with your arguments manually, but recommend run model by rest2() automatically with
        arguments by default.
        """
        warnings.filterwarnings("ignore")
        Angstrom_exponent[Angstrom_exponent > 2.5] = 2.5
        Angstrom_exponent[Angstrom_exponent < 0] = 0
        pressure[pressure > 1100] = 1100
        pressure[pressure < 300] = 300
        water_vapour[water_vapour > 10] = 10
        water_vapour[water_vapour < 0] = 0
        ozone[ozone > 0.6] = 0.6
        ozone[ozone < 0] = 0
        nitrogen_dioxide[nitrogen_dioxide > 0.03] = 0.03
        nitrogen_dioxide[nitrogen_dioxide < 0] = 0
        surface_albedo[surface_albedo > 1] = 1
        surface_albedo[surface_albedo < 0] = 0

        # air mass for aerosols extinction
        complex_temp = np.array(zenith_angle * 180. / np.pi, dtype=np.complex)

        ama = np.abs(np.power(np.cos(zenith_angle) + 0.16851 * np.power(complex_temp, 0.18198) / np.power(
            95.318 - complex_temp, 1.9542), -1))
        # air mass for water vapor absorption
        amw = np.abs(np.power(np.cos(zenith_angle) + 0.10648 * np.power(complex_temp, 0.11423) / np.power(
            93.781 - complex_temp, 1.9203), -1))
        # air mass for nitrogen dioxide absorption
        # amn = np.abs(np.power(np.cos(zenith_angle) + 1.1212 * np.power(zenith_angle * 180. / np.pi, 1.6132) / np.power(
        #   3.2629 - zenith_angle * 180. / np.pi, 1.9203), -1))
        # air mass for ozone absorption
        amo = np.abs(np.power(np.cos(zenith_angle) + 1.0651 * np.power(complex_temp, 0.6379) / np.power(
            101.8 - complex_temp, 2.2694), -1))
        # air mass for Rayleigh scattering and uniformly mixed gases absorption
        amR = np.abs(np.power(np.cos(zenith_angle) + 0.48353 * np.power(complex_temp, 0.095846) / np.power(
            96.741 - complex_temp, 1.754), -1))
        amRe = np.abs((pressure / 1013.25) * np.power(
            np.cos(zenith_angle) + 0.48353 * (np.power(complex_temp, 0.095846)) / np.power(
                96.741 - complex_temp, 1.754), -1))

        # Angstrom turbidity
        ang_beta = AOD550 / np.power(0.55, -1 * Angstrom_exponent)
        ang_beta[ang_beta > 1.1] = 1.1
        ang_beta[ang_beta < 0] = 0

        '''Band 1'''

        # transmittance for Rayleigh scattering
        TR1 = (1 + 1.8169 * amRe - 0.033454 * np.power(amRe, 2)) / (1 + 2.063 * amRe + 0.31978 * np.power(amRe, 2))
        # transmittance for uniformly mixed gases absorption
        Tg1 = (1 + 0.95885 * amRe + 0.012871 * np.power(amRe, 2)) / (1 + 0.96321 * amRe + 0.015455 * np.power(amRe, 2))
        # transmittance for Ozone absorption
        uo = ozone
        f1 = uo * (10.979 - 8.5421 * uo) / (1 + 2.0115 * uo + 40.189 * np.power(uo, 2))
        f2 = uo * (-0.027589 - 0.005138 * uo) / (1 - 2.4857 * uo + 13.942 * np.power(uo, 2))
        f3 = uo * (10.995 - 5.5001 * uo) / (1 + 1.6784 * uo + 42.406 * np.power(uo, 2))
        To1 = (1 + f1 * amo + f2 * np.power(amo, 2)) / (1 + f3 * amo)
        # transmittance for Nitrogen dioxide absorption
        un = nitrogen_dioxide
        g1 = (0.17499 + 41.654 * un - 2146.4 * np.power(un, 2)) / (1 + 22295. * np.power(un, 2))
        g2 = un * (-1.2134 + 59.324 * un) / (1 + 8847.8 * np.power(un, 2))
        g3 = (0.17499 + 61.658 * un + 9196.4 * np.power(un, 2)) / (1 + 74109. * np.power(un, 2))
        Tn1_middle = ((1 + g1 * amw + g2 * np.power(amw, 2)) / (1 + g3 * amw))
        Tn1_middle[Tn1_middle > 1] = 1
        Tn1 = Tn1_middle
        # Tn1 = min(1, ((1 + g1 * amw + g2 * np.power(amw, 2)) / (1 + g3 * amw)))
        Tn1166_middle = (1 + g1 * 1.66 + g2 * np.power(1.66, 2)) / (1 + g3 * 1.66)
        Tn1166_middle[Tn1166_middle > 1] = 1
        Tn1166 = Tn1166_middle
        # Tn1166 = min(1, ((1 + g1 * 1.66 + g2 * np.power(1.66, 2)) / (1 + g3 * 1.66)))  # atairmass = 1.66
        # transmittance for Water Vapor absorption
        h1 = water_vapour * (0.065445 + 0.00029901 * water_vapour) / (1 + 1.2728 * water_vapour)
        h2 = water_vapour * (0.065687 + 0.0013218 * water_vapour) / (1 + 1.2008 * water_vapour)
        Tw1 = (1 + h1 * amw) / (1 + h2 * amw)
        Tw1166 = (1 + h1 * 1.66) / (1 + h2 * 1.66)  # atairmass = 1.66

        # coefficients of angstrom_alpha
        AB1 = ang_beta
        alph1 = Angstrom_exponent
        d0 = 0.57664 - 0.024743 * alph1
        d1 = (0.093942 - 0.2269 * alph1 + 0.12848 * np.power(alph1, 2)) / (1 + 0.6418 * alph1)
        d2 = (-0.093819 + 0.36668 * alph1 - 0.12775 * np.power(alph1, 2)) / (1 - 0.11651 * alph1)
        d3 = alph1 * (0.15232 - 0.087214 * alph1 + 0.012664 * np.power(alph1, 2)) / (
                1 - 0.90454 * alph1 + 0.26167 * np.power(alph1, 2))
        ua1 = np.log(1 + ama * AB1)
        lam1 = (d0 + d1 * ua1 + d2 * np.power(ua1, 2)) / (1 + d3 * np.power(ua1, 2))

        # Aeroso transmittance
        ta1 = np.abs(AB1 * np.power(lam1, -1 * alph1))
        TA1 = np.exp(-ama * ta1)

        # Aeroso scattering transmittance
        TAS1 = np.exp(-ama * 0.92 * ta1)  # w1 = 0.92recommended

        # forward scattering fractions for Rayleigh extinction
        BR1 = 0.5 * (0.89013 - 0.0049558 * amR + 0.000045721 * np.power(amR, 2))

        # Aerosol scattering correction factor
        g0 = (3.715 + 0.368 * ama + 0.036294 * np.power(ama, 2)) / (1 + 0.0009391 * np.power(ama, 2))
        g1 = (-0.164 - 0.72567 * ama + 0.20701 * np.power(ama, 2)) / (1 + 0.0019012 * np.power(ama, 2))
        g2 = (-0.052288 + 0.31902 * ama + 0.17871 * np.power(ama, 2)) / (1 + 0.0069592 * np.power(ama, 2))
        F1 = (g0 + g1 * ta1) / (1 + g2 * ta1)

        # sky albedo
        rs1 = (0.13363 + 0.00077358 * alph1 + AB1 * (0.37567 + 0.22946 * alph1) / (1 - 0.10832 * alph1)) / (
                1 + AB1 * (0.84057 + 0.68683 * alph1) / (1 - 0.08158 * alph1))
        # ground albedo
        rg = surface_albedo

        '''Band 2'''

        # transmittance for Rayleigh scattering
        TR2 = (1 - 0.010394 * amRe) / (1 - 0.00011042 * np.power(amRe, 2))
        # transmittance for uniformly mixed gases absorption
        Tg2 = (1 + 0.27284 * amRe - 0.00063699 * np.power(amRe, 2)) / (1 + 0.30306 * amRe)
        # transmittance for Ozone absorption
        To2 = 1  # Ozone (none)
        # transmittance for Nitrogen dioxide absorption
        Tn2 = 1  # Nitrogen (none)
        Tn2166 = 1  # at air mass=1.66

        # transmittance for water vapor  absorption
        c1 = water_vapour * (19.566 - 1.6506 * water_vapour + 1.0672 * np.power(water_vapour, 2)) / (
                1 + 5.4248 * water_vapour + 1.6005 * np.power(water_vapour, 2))
        c2 = water_vapour * (0.50158 - 0.14732 * water_vapour + 0.047584 * np.power(water_vapour, 2)) / (
                1 + 1.1811 * water_vapour + 1.0699 * np.power(water_vapour, 2))
        c3 = water_vapour * (21.286 - 0.39232 * water_vapour + 1.2692 * np.power(water_vapour, 2)) / (
                1 + 4.8318 * water_vapour + 1.412 * np.power(water_vapour, 2))
        c4 = water_vapour * (0.70992 - 0.23155 * water_vapour + 0.096514 * np.power(water_vapour, 2)) / (
                1 + 0.44907 * water_vapour + 0.75425 * np.power(water_vapour, 2))
        Tw2 = (1 + c1 * amw + c2 * np.power(amw, 2)) / (1 + c3 * amw + c4 * np.power(amw, 2))
        Tw2166 = (1 + c1 * 1.66 + c2 * np.power(1.66, 2)) / (1 + c3 * 1.66 + c4 * np.power(1.66, 2))

        # coefficients of angstrom_alpha
        AB2 = ang_beta
        alph2 = Angstrom_exponent
        e0 = (1.183 - 0.022989 * alph2 + 0.020829 * np.power(alph2, 2)) / (1 + 0.11133 * alph2)
        e1 = (-0.50003 - 0.18329 * alph2 + 0.23835 * np.power(alph2, 2)) / (1 + 1.6756 * alph2)
        e2 = (-0.50001 + 1.1414 * alph2 + 0.0083589 * np.power(alph2, 2)) / (1 + 11.168 * alph2)
        e3 = (-0.70003 - 0.73587 * alph2 + 0.51509 * np.power(alph2, 2)) / (1 + 4.7665 * alph2)
        ua2 = np.log(1 + ama * AB2)
        lam2 = (e0 + e1 * ua2 + e2 * np.power(ua2, 2)) / (1 + e3 * ua2)

        # Aeroso transmittance
        lam2_temp = np.array(lam2, dtype=np.complex)
        ta2 = np.abs(AB2 * np.power(lam2_temp, -1 * alph2))
        TA2 = np.exp(-1 * ama * ta2)
        TAS2 = np.exp(-1 * ama * 0.84 * ta2)  # w2=0.84 recommended

        # forward scattering fractions for Rayleigh extinction
        BR2 = 0.5  # multi scatter negibile in Band 2
        # the aerosol forward scatterance factor
        Ba = 1 - np.exp(-0.6931 - 1.8326 * np.cos(zenith_angle))

        # Aerosol scattering correction
        h0 = (3.4352 + 0.65267 * ama + 0.00034328 * np.power(ama, 2)) / (1 + 0.034388 * np.power(ama, 1.5))
        h1 = (1.231 - 1.63853 * ama + 0.20667 * np.power(ama, 2)) / (1 + 0.1451 * np.power(ama, 1.5))
        h2 = (0.8889 - 0.55063 * ama + 0.50152 * np.power(ama, 2)) / (1 + 0.14865 * np.power(ama, 1.5))
        F2 = (h0 + h1 * ta2) / (1 + h2 * ta2)

        # sky albedo
        rs2 = (0.010191 + 0.00085547 * alph2 + AB2 * (0.14618 + 0.062758 * alph2) / (1 - 0.19402 * alph2)) / (
                1 + AB2 * (0.58101 + 0.17426 * alph2) / (1 - 0.17586 * alph2))

        # irradiance BAND1
        E0n1 = Eext * 0.46512
        # direct beam irradiance
        Ebn1 = E0n1 * TR1 * Tg1 * To1 * Tn1 * Tw1 * TA1

        # the incident diffuse irradiance on a perfectly absorbing ground
        Edp1 = E0n1 * np.cos(zenith_angle) * To1 * Tg1 * Tn1166 * Tw1166 * (
                BR1 * (1 - TR1) * np.power(TA1, 0.25) + Ba * F1 * TR1 * (1 - np.power(TAS1, 0.25)))
        # multiple reflections between the ground and the atmosphere
        Edd1 = rg * rs1 * (Ebn1 * np.cos(zenith_angle) + Edp1) / (1 - rg * rs1)

        # irradiance BAND2
        E0n2 = Eext * 0.51951
        # direct beam irradiance
        Ebn2 = E0n2 * TR2 * Tg2 * To2 * Tn2 * Tw2 * TA2
        # the incident diffuse irradiance on a perfectly absorbing ground
        Edp2 = E0n2 * np.cos(zenith_angle) * To2 * Tg2 * Tn2166 * Tw2166 * (
                BR2 * (1 - TR2) * np.power(TA2, 0.25) + Ba * F2 * TR2 * (1 - np.power(TAS2, 0.25)))
        # multiple reflections between the ground and the atmosphere
        Edd2 = rg * rs2 * (Ebn2 * np.cos(zenith_angle) + Edp2) / (1 - rg * rs2)
        # TOTALS BAND1+BAND2
        # direct horizontal irradiance
        Ebh = (Ebn1 + Ebn2) * np.cos(zenith_angle)
        dni = Ebn1 + Ebn2
        # correct for zenith angle
        dni[np.rad2deg(zenith_angle) > 90] = 0
        Ebh[np.rad2deg(zenith_angle) > 90] = 0
        # diffuse horizontal irradiance

        dhi = Edp1 + Edd1 + Edp2 + Edd2
        dhi[np.rad2deg(zenith_angle) > 90] = 0

        # global horizontal irradiance
        ghi = Ebh + dhi

        # Quality Control
        lower = 0
        ghi[ghi < lower] = np.nan
        dni[dni < lower] = np.nan
        dhi[dhi < lower] = np.nan

        ghi[np.isnan(ghi)] = 0
        dni[np.isnan(dni)] = 0
        dhi[np.isnan(dhi)] = 0

        return [ghi, dni, dhi]
    

    def REST2v5(self):
        """
        run rest2 model with arguments downloaded in data set

        This model is called the REST2v5 clear sky model, written and designed by
        Christian A. Gueymard over a series of publications, though primarily in
        his 2008 paper in the Journal of Solar Energy (volume 82, issue 3, pages
        272-285) titled "REST2: High-performance solar radiation model for
        cloudless-sky irradiance,  illuminance, and photosynthetically active
        radiation - Validation with a benchmark dataset"

        :return: [ghi, dni, dhi]
        """


        same_flag = 1

        for i in range(len(self.time) - 1):
            if self.time[i + 1].shape == self.time[0].shape:
                if (self.time[i + 1] != self.time[0]).any():
                    same_flag = 0
            else:
                same_flag = 0

        if same_flag == 1:
            zenith_angle = latlon2solarzenith(self.lat, self.lon, self.time.T)
            zenith_angle = np.deg2rad(zenith_angle)
            Eext = data_eext_builder(self.time.T)

            [tot_aer_ext, AOD550, Angstrom_exponent, ozone, surface_albedo, water_vapour, pressure,
             nitrogen_dioxide] =extract_for_MERRA2(self.lat, self.lon, self.time.T, self.elev, self.datadir)

            [ghi, dni, dhi] = self.clear_sky_REST2V5(zenith_angle, Eext, pressure, water_vapour,ozone, nitrogen_dioxide, AOD550,Angstrom_exponent, surface_albedo)
            if self.pandas_output:
                col_index = ['GHI', 'DNI', 'DIF']
                station_data_list = []
                for index in range(len(self.time)):
                    time_temp = (self.time[index]).reshape(self.time[index].size, 1)
                    row_index = time_temp[:, 0]
                    station_data = pd.DataFrame(np.hstack((ghi[:, index][:, np.newaxis], dni[:, index][:, np.newaxis], dhi[:, index][:, np.newaxis])), index=row_index, columns=col_index)
                    station_data_list.append(station_data)

                return station_data_list

            else:
                ghi = ghi.T
                dni = dni.T
                dhi = dhi.T

                return [ghi, dni, dhi]

        else:
            ghi = []
            dni = []
            dhi = []
            col_index = ['GHI', 'DNI', 'DIF']
            station_data_list = []

            for index in range(len(self.time)):
                time_temp = (self.time[index]).reshape(self.time[index].size, 1)
                zenith_angle = latlon2solarzenith(self.lat[index], self.lon[index], time_temp)
                row_index = time_temp[:, 0]
                zenith_angle = np.deg2rad(zenith_angle)
                Eext = data_eext_builder(time_temp)

                [tot_aer_ext, AOD550, Angstrom_exponent, ozone, surface_albedo, water_vapour, pressure,
                 nitrogen_dioxide] = extract_for_MERRA2(self.lat[index], self.lon[index], time_temp, self.elev[index], self.datadir)

                [ghi_i, dni_i, dhi_i] = self.clear_sky_REST2V5(zenith_angle, Eext, pressure, water_vapour, ozone,
                                                         nitrogen_dioxide, AOD550, Angstrom_exponent, surface_albedo)

                if self.pandas_output:
                    station_data = pd.DataFrame(np.hstack((ghi_i, dni_i, dhi_i)), index=row_index, columns=col_index)
                    station_data_list.append(station_data)
                else:
                    ghi.append(ghi_i)
                    dni.append(dni_i)
                    dhi.append(dhi_i)
            if self.pandas_output:
                return station_data_list
            else:
                return [ghi, dni, dhi]

