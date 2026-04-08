#!/usr/bin/python

import sys
import csv

# import xlrd
# import xlwt not work due to the 256 column limit
# import xlsxwriter
# from scipy import stats

# do lowess fit. https://stackoverflow.com/questions/36252434/predicting-on-new-data-using-locally-weighted-regression-loess-lowess
import numpy as np

from scipy.stats import spearmanr

# from moepy import lowess
# import matplotlib.pyplot as plt

from collections import defaultdict
from collections import OrderedDict
import bisect

# import json
# from _ast import Return
# from matplotlib import collections
import re
from _collections import defaultdict

# from builtins import True

debug = False


class Glycans:
    def __init__(self):
        self.glycans = [
            ["M3F", 2, 3, 1, 0, 0],
            ["M4F", 2, 4, 1, 0, 0],
            ["M5F", 2, 5, 1, 0, 0],
            ["A1G0", 3, 3, 0, 0, 0],
            ["A1G0F", 3, 3, 1, 0, 0],
            ["A2G0", 4, 3, 0, 0, 0],
            ["A2G0F", 4, 3, 1, 0, 0],
            ["A1G1", 3, 4, 0, 0, 0],
            ["A1G1F", 3, 4, 1, 0, 0],
            ["A2G1", 4, 4, 0, 0, 0],
            ["A2G1F", 4, 4, 1, 0, 0],
            ["A2G2", 4, 5, 0, 0, 0],
            ["A2G2F", 4, 5, 1, 0, 0],
            ["A2G3F", 4, 6, 1, 0, 0],
            ["A2G4", 4, 7, 0, 0, 0],
            ["A2G4F", 4, 7, 1, 0, 0],
            ["A3G0", 5, 3, 0, 0, 0],
            ["A3G0F", 5, 3, 1, 0, 0],
            ["A3G1", 5, 4, 0, 0, 0],
            ["A3G1F", 5, 4, 1, 0, 0],
            ["A3G2", 5, 5, 0, 0, 0],
            ["A3G2F", 5, 5, 1, 0, 0],
            ["A3G3", 5, 6, 0, 0, 0],
            ["A3G3F", 5, 6, 1, 0, 0],
            ["A3G4F", 5, 7, 1, 0, 0],
            ["A3G5F", 5, 8, 1, 0, 0],
            ["A3G6F", 5, 9, 1, 0, 0],
            ["A4G3F", 6, 6, 1, 0, 0],
            ["A4G4F", 6, 7, 1, 0, 0],
            ["A4G5F", 6, 8, 1, 0, 0],
            ["A4G6F", 6, 9, 1, 0, 0],
            ["A4G7F", 6, 10, 1, 0, 0],
            ["A4G8F", 6, 11, 1, 0, 0],
            ["A2G2F2 (LeX)", 4, 5, 2, 0, 0],
            ["A2G3F2 (LeX)", 4, 6, 2, 0, 0],
            ["A3G3F2 (LeX)", 5, 6, 2, 0, 0],
            ["A3G4F2 (LeX)", 5, 7, 2, 0, 0],
            ["A3G5F2 (LeX)", 5, 8, 2, 0, 0],
            ["A3G4F3 (LeX)", 5, 7, 3, 0, 0],
            ["A1S1G1", 3, 4, 0, 1, 0],
            ["A1S1G1F", 3, 4, 1, 1, 0],
            ["A2S1G1", 4, 4, 0, 1, 0],
            ["A2S1G1F", 4, 4, 1, 1, 0],
            ["A2S1G2", 4, 5, 0, 1, 0],
            ["A2S2G2", 4, 5, 0, 2, 0],
            ["A2S1G2F", 4, 5, 1, 1, 0],
            ["A2S1G3F", 4, 6, 1, 1, 0],
            ["A2S2G2F", 4, 5, 1, 2, 0],
            ["A3S1G2", 5, 5, 0, 1, 0],
            ["A2Sg1G1F", 4, 4, 1, 0, 1],
            ["A2Sg1G2F", 4, 5, 1, 0, 1],
            ["A2Sg1G3F", 4, 6, 1, 0, 1],
            ["A2Sg2G2F", 4, 5, 1, 0, 2],
            ["A2S1Sg1G2F", 4, 5, 1, 1, 1],
            ["A3Sg1G2F", 5, 5, 1, 0, 1],
            ["A3Sg1G3F", 5, 6, 1, 0, 1],
            ["A3Sg1G4F", 5, 7, 1, 0, 1],
            ["A3Sg1G5F", 5, 8, 1, 0, 1],
            ["A3Sg2G3F", 5, 6, 1, 0, 2],
            ["A3Sg2G4F", 5, 7, 1, 0, 2],
            ["A3Sg3G3F", 5, 6, 1, 0, 3],
            ["A2Sg1G2F2 (LeX)", 4, 5, 2, 0, 1],
            ["A3Sg1G3F2 (LeX)", 5, 6, 2, 0, 1],
            ["A3Sg1G4F2 (LeX)", 5, 7, 2, 0, 1],
            ["A3Sg2G3F2 (LeX)", 5, 6, 2, 0, 2],
            ["A1G0M4", 3, 4, 0, 0, 0],
            ["A1G1M4", 3, 5, 0, 0, 0],
            ["A1G0M4F", 3, 4, 1, 0, 0],
            ["A1G1M4F", 3, 5, 1, 0, 0],
            ["A1G0M5", 3, 5, 0, 0, 0],
            ["A1G1M5", 3, 6, 0, 0, 0],
            ["A1G0M5F", 3, 5, 1, 0, 0],
            ["A1G1M5F", 3, 6, 1, 0, 0],
            ["A1G1M6", 3, 7, 0, 0, 0],
            ["A1G2M4F", 3, 6, 0, 0, 0],
            ["A1G2M5", 3, 7, 0, 0, 0],
            ["A1G2M4F", 3, 6, 1, 0, 0],
            ["A1G2M5F", 3, 7, 1, 0, 0],
            ["A2G1M5F", 4, 6, 1, 0, 0],
            ["A2G2M5F", 4, 7, 1, 0, 0],
            ["A2G3M5F", 4, 8, 1, 0, 0],
            ["A1S1G1M4F", 3, 5, 1, 1, 0],
            ["A1S1G1M5F", 3, 6, 1, 1, 0],
            ["A1Sg1G1M4F", 3, 5, 1, 0, 1],
            ["A1Sg1G1M5", 3, 6, 0, 0, 1],
            ["A1Sg1G1M5F", 3, 6, 1, 0, 1],
            ["M3", 2, 3, 0, 0, 0],
            ["M4", 2, 4, 0, 0, 0],
            ["M5", 2, 5, 0, 0, 0],
            ["M6", 2, 6, 0, 0, 0],
            ["M7", 2, 7, 0, 0, 0],
            ["M8", 2, 8, 0, 0, 0],
            ["M9", 2, 9, 0, 0, 0],
        ]
        self.comp_to_name_dict = {}

        for i in range(len(self.glycans)):
            name = self.glycans[i][0]
            composition = tuple(self.glycans[i][1:])
            if composition in self.comp_to_name_dict:
                self.comp_to_name_dict[composition].append(name)
            else:
                self.comp_to_name_dict[composition] = [name]

    # return motif from composition format(Byonic format)
    # HexNAc(4)Hex(5)Fuc(1)NeuAc(1)NeuGc(1)
    # HexNAc(5)Hex(6)NeuGc(2)
    # high mannose glycans, fucosylated glycans, or sialylated glycans
    def getGlycanMotif(self, compositionStr, newName):
        rtn = []
        if "Fuc(" in compositionStr:
            rtn.append("Fucosylation")
        else:
            rtn.append("Afucosylation")

        if "M" in newName:
            rtn.append("High mannose")

        if "NeuAc" in compositionStr or "NeuGc" in compositionStr:
            rtn.append("Sialylation")

        if "NeuAc" in compositionStr:
            rtn.append("NANA")

        if "NeuGc" in compositionStr:
            rtn.append("NGNA")

        if "LeX" in newName:
            rtn.append("LewisX")

        # be careful! newName may be the same as compositionStr (when there is no match)
        if "G" in newName and "G0" not in newName and "Gc" not in newName:
            rtn.append("Galactosylation")

        return rtn


def get_glycan_composition_list(compositionName):
    """
    Convert glycan composition to a len-5 list
    example name HexNAc(4)Hex(5)Fuc(1)NeuAc(1)NeuGc(1)
    output as [4,5,1,1,1]
    """
    if not compositionName:
        return [0, 0, 0, 0, 0]

    comps = compositionName.split(")")
    # In the list, 5 elements are
    # GlcNac Hex (Gal and Man are both Hex) Fuc NeuAc  NeuGc
    compList = [0, 0, 0, 0, 0]
    # print(compositionName, comps)
    for comp in comps:
        if len(comp) == 0:
            continue
        tmp = comp.split("(")
        glycan, cnt = tmp[0], int(tmp[1])
        if glycan == "HexNAc":
            compList[0] = cnt
        elif glycan == "Hex":
            compList[1] = cnt
        elif glycan == "Fuc":
            compList[2] = cnt
        elif glycan == "NeuAc":
            compList[3] = cnt
        elif glycan == "NeuGc":
            compList[4] = cnt
        else:
            # unknowntype
            compList = [0, 0, 0, 0, 0]
            break
    return compList


def glycan_name_old_to_new(compositionName, comp_to_name_dict):
    compList = get_glycan_composition_list(compositionName)
    key = tuple(compList)
    if key in comp_to_name_dict:
        return "/".join(comp_to_name_dict[key])
    else:
        return compositionName


def writeToCSV(filename, fields, rows):
    # writing to csv file
    with open(filename, "w") as csvfile:
        # creating a csv writer object
        csvwriter = csv.writer(csvfile)

        # writing the fields
        csvwriter.writerow(fields)

        # writing the data rows
        csvwriter.writerows(rows)


def mean(list):
    if len(list) == 0:
        return 0
    total = sum(list)
    return total / len(list)


def std(list):
    if (len(list)) <= 1:
        return 0
    m = mean(list)
    total = 0
    for x in list:
        total += (x - m) * (x - m)
    return (total / (len(list) - 1)) ** (0.5)


def std_error(list):
    if (len(list)) <= 1:
        return 0
    # Standard error = Standard deviation/ sqrt(n)
    # https://www.radford.edu/~biol-web/stats/standarderrorcalc.pdf
    return std(list) / (len(list)) ** (0.5)


def cv(list):
    m = mean(list)
    s = std(list)
    if m == 0:
        return 0
    return s * 1.0 / m


def pvalue_from_ttest(list1, list2):
    # remove 0
    a = []
    b = []
    for x in list1:
        if x == 0:
            # a.append('nan')
            pass
        else:
            a.append(x)

    for x in list2:
        if x == 0:
            # b.append('nan')
            pass
        else:
            b.append(x)

    if len(a) == 0 or len(b) == 0:
        return "nan"

    # two independent sample t-test
    twosample_results = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
    return twosample_results[1]


def get_peplength_from_sequence(sequence):
    # remove modifications in the sequence, for example, "PEPT[123]IDE" should be "PEPTIDE"
    sequence = str(sequence)
    sequence = re.sub(r"\[.*?\]", "", sequence)
    sequence = re.sub(r"\(.*?\)", "", sequence)
    # for P.PEPTIDE.K, should be PEPTIDE
    if len(sequence) > 3 and sequence[1] == "." and sequence[-2] == ".":
        sequence = sequence[2:-2]
    return len(sequence)


def main1(parameterList, glycanColumnName="Glycan Composition"):
    filename = parameterList[1]
    fdr2dThreshold = float(parameterList[2])
    byonicThreshold = float(parameterList[3])
    ppmThreshold = float(parameterList[4])
    peplengthThreshold = int(parameterList[5])
    filter = parameterList[6]  # controls weather export all or only glycan.
    mincountThreshold = int(parameterList[7])
    conditionStr = parameterList[8]
    abundanceType = parameterList[9]

    conditions = conditionStr.split("---")

    proteinColumnName = "Protein Accessions"
    modPostionColumnName = "Position in Protein"
    # use "Modifications (all possible sites)" because Modition column tends to have ID like [S/T] rather than [S100; T200]
    # modPostionInPeptideColumnName = "Modifications"
    modPostionInPeptideColumnName = "Modifications (all possible sites)"
    abundanceColumnName = abundanceType + ": "
    proteinDescriptionColumnName = "Master Protein Descriptions"

    fdr2dColumnName = "FDR 2D (by Search Engine)"
    byonicColumnName = "Byonic Score ("
    ppmColumnName = "DeltaM [ppm] "
    pepColumnName = "Sequence"

    glycan_dict = {}
    parts = filename.split(".")
    outputFile = ".".join(parts[:-1]) + "_results.csv"
    qc_outputFile = ".".join(parts[:-1]) + "_qc.csv"
    # metadata
    site_table_metaFile = ".".join(parts[:-1]) + ".sites_table.json"
    metaFile_global = ".".join(parts[:-1]) + "_global.json"
    # outputFileJson = ".".join(parts[:-1]) + "_full.json"

    file_id = parts[-2].split("_")[-1]
    # proportion file for heatmap
    proportion_file = "uploads/proportions_table_" + file_id + ".csv"
    condition_map_file = "uploads/conditions_biological_replicates_map.csv"

    rows = []
    fields = []
    site_to_rows = defaultdict(list)

    if parts[-1].lower() == "csv":
        # csv file
        pass
    elif parts[-1].lower() == "tsv":
        pass
    elif parts[-1].lower() == "xls" or parts[-1].lower() == "xlsx":
        # To open Workbook, use first row by default
        wb = xlrd.open_workbook(filename)
        sheet = wb.sheet_by_index(0)

        # get column headers
        fields = sheet.row_values(0) + [
            "Protein---Position---Gene",
            "Converted Glycan Names",
        ]
        # add glycan composition, request by Niclas
        fields += ["HexNAc", "Hex", "Fuc", "NeuAc", "NeuGc"]

        # add conditions columns
        condition_valid_count_fields = []
        condition_fields = []
        condition_std_fields = []
        condition_stderr_fields = []
        condition_cv_fields = []

        # print(fields)

        glycan = Glycans()
        comp_to_name_dict = glycan.comp_to_name_dict

        # get location of the glycan column
        index_of_glycan_col = sheet.row_values(0).index(glycanColumnName)
        index_of_protein_col = sheet.row_values(0).index(proteinColumnName)
        # According to Niclas, modPos is peptide starting position.Need to correct with  mod posiion in peptide
        index_of_modPos_col = sheet.row_values(0).index(modPostionColumnName)
        # fix msfragger. msfragger does not contain "Modifications (all possible sites)"   column
        if modPostionInPeptideColumnName not in sheet.row_values(0):
            modPostionInPeptideColumnName = (
                modPostionInPeptideColumnName
            ) = "Modifications"
        index_of_modPos_in_peptide_col = sheet.row_values(0).index(
            modPostionInPeptideColumnName
        )

        index_of_description_col = sheet.row_values(0).index(
            proteinDescriptionColumnName
        )

        index_of_pep_col = sheet.row_values(0).index(pepColumnName)
        # add sanity check in the future to avoid have no such columns
        index_of_fdr2d_col = [
            i
            for i, x in enumerate(sheet.row_values(0))
            if x.startswith(fdr2dColumnName)
        ][0]
        index_of_byonic_col = [
            i
            for i, x in enumerate(sheet.row_values(0))
            if x.startswith(byonicColumnName)
        ][0]
        index_of_ppm_col = [
            i for i, x in enumerate(sheet.row_values(0)) if x.startswith(ppmColumnName)
        ][0]

        index_of_abd_col = [
            i
            for i, x in enumerate(sheet.row_values(0))
            if x.startswith(abundanceColumnName)
        ]
        name_of_abd_col = [
            x
            for i, x in enumerate(sheet.row_values(0))
            if x.startswith(abundanceColumnName)
        ]

        uniqueConditions = []
        condition_to_indexes = defaultdict(list)
        pos = 0
        idx_to_condition = {}

        for condition in conditions:
            if condition not in uniqueConditions:
                uniqueConditions.append(condition)
            condition_to_indexes[condition].append(index_of_abd_col[pos])
            idx_to_condition[index_of_abd_col[pos]] = condition
            pos += 1

        for condition in uniqueConditions:
            condition_valid_count_fields.append(condition + ": Valid Data Points")
            condition_fields.append(condition + ": Abundance")
            condition_std_fields.append(condition + ": std")
            condition_stderr_fields.append(condition + ": std_error")
            condition_cv_fields.append(condition + ": cv")
        fields += (
            condition_valid_count_fields
            + condition_fields
            + condition_std_fields
            + condition_stderr_fields
            + condition_cv_fields
        )

        # add p value fields for each combinations
        for f in range(len(uniqueConditions)):
            for s in range(f + 1, len(uniqueConditions)):
                fields.append(
                    "p-value:" + uniqueConditions[f] + "_to_" + uniqueConditions[s]
                )

        # for more than 2 conditions, include anova
        if len(uniqueConditions) > 2:
            fields.append("ANOVA_F-statistic")
            fields.append("ANOVA_P-value")

        # global glycan
        global_glycan_stats = {}
        global_glycan_stats["condition_names"] = uniqueConditions
        global_glycan_stats["col_names"] = name_of_abd_col

        glycan_to_abd_replicates = defaultdict(list)
        glycan_to_abd_conditions = defaultdict(lambda: defaultdict(float))
        motif_to_abd_replicates = defaultdict(list)
        motif_to_abd_conditions = defaultdict(lambda: defaultdict(float))

        glycan_to_cnt_replicates = defaultdict(list)
        glycan_to_cnt_conditions = defaultdict(lambda: defaultdict(int))
        motif_to_cnt_replicates = defaultdict(list)
        motif_to_cnt_conditions = defaultdict(lambda: defaultdict(int))

        # For single protein plot, record condition mean and stderr in order to add error bar
        condition_mean_and_stderr = defaultdict(lambda: defaultdict(list))

        # proprotion table for each unique glyco peptide
        glycopep_to_abd_replicates = defaultdict(list)

        resultRowNumber = 0
        resultGlycoPeptideCount = 0

        for i in range(1, sheet.nrows):
            glycan_names = sheet.cell_value(i, index_of_glycan_col)
            # print(glycan_names)
            newName = ""
            # applying filters
            peplength_col = get_peplength_from_sequence(
                sheet.cell_value(i, index_of_pep_col)
            )
            fdr2d_col = float(sheet.cell_value(i, index_of_fdr2d_col))
            byonic_col = float(sheet.cell_value(i, index_of_byonic_col))
            ppm_col = float(sheet.cell_value(i, index_of_ppm_col))
            """ below are filters from parameter list
                fdr2dThreshold = float(parameterList[2])
                byonicThreshold = float(parameterList[3])
                ppmThreshold = float(parameterList[4])
                peplengthThreshold = int(parameterList[5])
                filter = parameterList[6]         # controls weather export all or only glycan.
                mincountThreshold = int(parameterList[7]) 
            """
            if peplength_col < peplengthThreshold:
                continue
            if fdr2d_col > fdr2dThreshold:
                continue
            if byonic_col < byonicThreshold:
                continue
            if abs(ppm_col) > ppmThreshold:
                continue

            countOfPeaks = 0
            for c in index_of_abd_col:
                abdStr = str(sheet.cell_value(i, c))
                if len(abdStr) > 0 and float(abdStr) > 0:
                    countOfPeaks += 1
            if countOfPeaks < mincountThreshold:
                continue

            condition_to_abd_list = defaultdict(list)
            # print condition_to_indexes
            # condition_cv_data = defaultdict(list)
            for condition in uniqueConditions:
                for idx in condition_to_indexes[condition]:
                    abd = sheet.cell_value(i, idx)  # value returned from excel is float
                    if not abd:
                        # abd = 0
                        # WL 090320 do not convert empty values to 0.
                        continue
                    abd = float(abd)
                    condition_to_abd_list[condition].append(abd)

            # store the best glycan name to display in the 5 glycan composition columns
            best_glycan_name = ""
            site = ""

            if len(glycan_names) > 0:
                resultGlycoPeptideCount += 1
                mods = glycan_names.split("; ")
                for j in range(len(mods)):
                    if j > 0:
                        newName += ";"
                    if mods[j] not in glycan_dict:
                        glycan_dict[mods[j]] = glycan_name_old_to_new(
                            mods[j], comp_to_name_dict
                        )
                    # if a notation exist, store it as the best glycan name
                    if glycan_dict[mods[j]] != mods[j] and best_glycan_name == "":
                        best_glycan_name = mods[j]
                    newName += glycan_dict[mods[j]]

                # if NO notation exist, store the first original name
                if best_glycan_name == "":
                    best_glycan_name = mods[0]

                proteinDescription = sheet.cell_value(i, index_of_description_col)

                geneName = ""
                geneIdx = proteinDescription.find(" GN=")
                if geneIdx > 0:
                    geneName = proteinDescription[geneIdx + 4 :].split(" ")[0]

                # site
                peptide_start_site = int(
                    float(sheet.cell_value(i, index_of_modPos_col))
                )
                mod_site_in_peptide_str = sheet.cell_value(
                    i, index_of_modPos_in_peptide_col
                )
                mod_site_in_peptide = str(peptide_start_site)
                # format is
                # 2xCarbamidomethyl [C7; C24]; 1xHexNAc(5)Hex(6)NeuAc(1) [N10]
                tmp_list = mod_site_in_peptide_str.split(glycan_names.split(";")[0])
                # tmp_list looks like [2xCarbamidomethyl [C7; C24]; 1x,  [N10]]
                if len(tmp_list) > 1:
                    tmp2_list = tmp_list[1].split("[")
                    # tmp2_list is like [" ", "N10; N33"]
                    tmp3_list = tmp2_list[1].split(";")
                    # tmp3_list is like ["N10", " N33"]
                    residue = tmp3_list[0][0]
                    # residue_loc = int(tmp3_list[0][1:].split("]")[0])
                    residue_loc_str = tmp3_list[0][1:].split("]")[0]
                    if len(residue_loc_str) > 0:
                        residue_loc_str = str(
                            int(residue_loc_str) + peptide_start_site - 1
                        )
                        mod_site_in_peptide = residue + residue_loc_str
                    # mod_site_in_peptide = residue + str(peptide_start_site + residue_loc - 1)

                site = (
                    sheet.cell_value(i, index_of_protein_col)
                    + "---"
                    + mod_site_in_peptide
                    + "---"
                    + geneName
                )
                site_to_rows[site].append(resultRowNumber + 1)

                site_with_glycan = newName + "---" + site

                if newName not in glycan_to_abd_replicates:
                    glycan_to_abd_replicates[newName] = [0] * len(index_of_abd_col)
                    glycan_to_cnt_replicates[newName] = [0] * len(index_of_abd_col)

                if site_with_glycan not in glycopep_to_abd_replicates:
                    glycopep_to_abd_replicates[site_with_glycan] = [0] * len(
                        index_of_abd_col
                    )

                motifs = glycan.getGlycanMotif(glycan_names, newName)
                k = 0
                for idx in index_of_abd_col:
                    # add global staticis for glycans
                    abd = sheet.cell_value(i, idx)  # value returned from excel is float
                    curr_condition = idx_to_condition[idx]
                    if not abd:
                        abd = 0
                    abd = float(abd)
                    glycan_to_abd_replicates[newName][k] += abd
                    glycan_to_abd_conditions[newName][curr_condition] += abd
                    glycopep_to_abd_replicates[site_with_glycan][k] += abd

                    for motif in motifs:
                        if motif not in motif_to_abd_replicates:
                            motif_to_abd_replicates[motif] = [0] * len(index_of_abd_col)
                            motif_to_cnt_replicates[motif] = [0] * len(index_of_abd_col)
                        motif_to_abd_replicates[motif][k] += abd
                        motif_to_abd_conditions[motif][curr_condition] += abd
                        if abd > 0:
                            motif_to_cnt_replicates[motif][k] += 1
                            motif_to_cnt_conditions[motif][curr_condition] += 1

                    if abd > 0:
                        glycan_to_cnt_replicates[newName][k] += 1
                        glycan_to_cnt_conditions[newName][curr_condition] += 1

                    k += 1

            # append condition means, std and cvs
            tmp = []
            for condition in uniqueConditions:
                tmp.append(len(condition_to_abd_list[condition]))
            for condition in uniqueConditions:
                tmp.append(mean(condition_to_abd_list[condition]))
            for condition in uniqueConditions:
                tmp.append(std(condition_to_abd_list[condition]))
            for condition in uniqueConditions:
                tmp.append(std_error(condition_to_abd_list[condition]))
            for condition in uniqueConditions:
                tmp.append(cv(condition_to_abd_list[condition]))

            # for single protein, save
            if "single_protein" in filename:
                for condition in uniqueConditions:
                    condition_mean_and_stderr[newName][condition].append(
                        mean(condition_to_abd_list[condition])
                    )
                    condition_mean_and_stderr[newName][condition].append(
                        std_error(condition_to_abd_list[condition])
                    )

            # add p value fields
            for f in range(len(uniqueConditions)):
                for s in range(f + 1, len(uniqueConditions)):
                    tmp.append(
                        pvalue_from_ttest(
                            condition_to_abd_list[uniqueConditions[f]],
                            condition_to_abd_list[uniqueConditions[s]],
                        )
                    )

            # more than 2 condition, append anova
            if len(uniqueConditions) > 2:
                param_list = []
                for condition in uniqueConditions:
                    # change 0 to nan
                    param_list.append(
                        [
                            "nan" if x == 0 else x
                            for x in condition_to_abd_list[condition]
                        ]
                    )
                # * is used for dynamic params. https://stackoverflow.com/questions/18759923/python-create-a-dynamic-list-of-parameter-for-a-method
                anova_results = stats.f_oneway(*param_list)
                tmp.append(anova_results[0])
                tmp.append(anova_results[1])

            if filter == "all":
                rows.append(
                    sheet.row_values(i)
                    + [site]
                    + [newName]
                    + get_glycan_composition_list(best_glycan_name)
                    + tmp
                )
                resultRowNumber += 1
            elif filter == "glycan":
                if len(glycan_names) > 0:
                    rows.append(
                        sheet.row_values(i)
                        + [site]
                        + [newName]
                        + get_glycan_composition_list(best_glycan_name)
                        + tmp
                    )
                    resultRowNumber += 1

        writeToCSV(outputFile, fields, rows)

        # save a copy in json format
        # with open(outputFileJson, 'w') as fp:
        #    json.dump(rows, fp)

        # save to json
        with open(site_table_metaFile, "w") as fp:
            json.dump(site_to_rows, fp)

        global_glycan_stats["glycan_to_abd_replicates"] = glycan_to_abd_replicates
        global_glycan_stats["glycan_to_abd_conditions"] = glycan_to_abd_conditions
        global_glycan_stats["motif_to_abd_replicates"] = motif_to_abd_replicates
        global_glycan_stats["motif_to_abd_conditions"] = motif_to_abd_conditions

        global_glycan_stats["glycan_to_cnt_replicates"] = glycan_to_cnt_replicates
        global_glycan_stats["glycan_to_cnt_conditions"] = glycan_to_cnt_conditions
        global_glycan_stats["motif_to_cnt_replicates"] = motif_to_cnt_replicates
        global_glycan_stats["motif_to_cnt_conditions"] = motif_to_cnt_conditions
        global_glycan_stats["condition_mean_and_stderr"] = condition_mean_and_stderr

        with open(metaFile_global, "w") as fp:
            json.dump(global_glycan_stats, fp, sort_keys=False)

        rtn = dict()
        rtn["outputFile"] = outputFile
        rtn["site_to_rows"] = site_to_rows

        # save condition names table
        conditions_rep_rows = [[], [], [], []]
        for i in range(len(global_glycan_stats["col_names"])):
            conditions_rep_rows[0].append(i + 1)
            conditions_rep_rows[1].append(uniqueConditions.index(conditions[i]) + 1)
            conditions_rep_rows[2].append("MAP1")
            conditions_rep_rows[3].append(conditions[i])

        with open(condition_map_file, "w") as csvfile:
            # creating a csv writer object
            csvwriter = csv.writer(csvfile)
            # writing the data rows
            csvwriter.writerows(conditions_rep_rows)

        # save proprotion table for site glycan
        prop_rows = []
        fields = ["Gene", "Protein"]
        for i in range(len(global_glycan_stats["col_names"])):
            fields.append("Est_Prop" + str(i + 1))

        # second and third lines are sample names. Remove them during heatmap processing..
        prop_rows.append(global_glycan_stats["col_names"])
        prop_rows.append(conditions)
        prop_rows.append(uniqueConditions)
        prop_rows.append(conditions_rep_rows[1])

        for k in glycopep_to_abd_replicates.keys():
            tmp_gene = k.split("---")[-1]
            if len(tmp_gene) == 0:
                tmp_gene = "NA"
            tmp_total = sum(glycopep_to_abd_replicates[k])
            tmp_row = []
            for v in glycopep_to_abd_replicates[k]:
                if v == 0 or tmp_total == 0:
                    tmp_row.append("")
                else:
                    tmp_row.append(v / tmp_total)
            # keep not use gene here, just use all information
            # prop_rows.append([tmp_gene, k] + tmp_row)
            prop_rows.append([k, k] + tmp_row)
        writeToCSV(proportion_file, fields, prop_rows)
        # condition_fields.append(condition + ": Abundance")
        # global_glycan_stats['col_names']

        # get some QC/statistics
        # number of total proteins, number of total glycans, number of unique glycans, number of glycan sites, and number of unique glycan sites per protein... and number of peptides
        statistics = OrderedDict()
        proteinSet = set()
        for k in site_to_rows.keys():
            proteinSet.add(k.split("---")[0])

        statistics["total_proteins"] = len(proteinSet)
        statistics["total_peptides"] = resultRowNumber
        statistics["total_glycopeptides"] = resultGlycoPeptideCount
        statistics["unique_glycans"] = len(
            global_glycan_stats["glycan_to_abd_replicates"]
        )
        statistics["total_sites"] = len(site_to_rows)

        rtn["statistics"] = statistics

        # store qc info into a downloadable file. Request by Niclas
        qc_fields = [
            "total_proteins",
            "total_peptides",
            "total_glycopeptides",
            "unique_glycans",
            "total_sites",
        ]
        qc_rows = []
        tmp_row = []
        for field in qc_fields:
            tmp_row.append(statistics[field])
        qc_rows.append(tmp_row)
        writeToCSV(qc_outputFile, qc_fields, qc_rows)
        rtn["qc_output_file"] = qc_outputFile

        # use python 2 here.
        # print json.dumps(rtn)


def get_protein_ranks_from_unmod_run(protein_file_path, protein_file_id_column):
    protein_ranks = OrderedDict()
    # read protein file
    separator = "\t" if protein_file_path.lower().endswith((".tsv")) else ","

    idx_protein_id = -1
    with open(protein_file_path) as fd:
        rd = csv.reader(fd, delimiter=separator, quotechar='"')
        cnt = 0
        for row in rd:
            if cnt == 0:
                # it is header
                if protein_file_id_column in row:
                    idx_protein_id = row.index(protein_file_id_column)
                else:
                    raise Exception(protein_file_id_column + "not in file header")
            else:
                if row[idx_protein_id] in protein_ranks:
                    protein_ranks[row[idx_protein_id]] += 1
                else:
                    protein_ranks[row[idx_protein_id]] = 1
            cnt += 1

    return OrderedDict(sorted(protein_ranks.items(), key=lambda t: t[1], reverse=True))


# fasta file iterator to get a subset
def get_fasta_subset(fasta_file_path, protein_ranks):
    fasta_subset = {}
    # Using readline()
    fasta_file = open(fasta_file_path, "r")
    pro_count = 0

    current_accession = ""
    pro_seq = ""
    while True:
        # Get next line from file
        line = fasta_file.readline()
        # if line is empty
        # end of file is reached
        if not line:
            break

        line = line.strip()
        if line.startswith(">"):
            if len(pro_seq) > 0:
                if current_accession in protein_ranks:
                    fasta_subset[current_accession] = pro_seq
                pro_seq = ""
            pro_count += 1
            current_accession = line.split(" ")[0][1:]
        else:
            pro_seq += line

    if len(pro_seq) > 0:
        fasta_subset[current_accession] = pro_seq
        pro_seq = ""

    fasta_file.close()
    return fasta_subset


def remap_peptide(clean_peptide, protein_ranks, fasta_subset):
    # note that protein_ranks is sorted by value
    for k, v in protein_ranks.items():
        protein_only = k
        gene_only = ""
        fasta_seq = fasta_subset[protein_only]
        if clean_peptide in fasta_seq:
            return protein_only

    return ""


def remapping(
    ptm_file_path,
    protein_ranks,
    fasta_subset,
    ptm_file_id_column,
    ptm_file_peptide_column,
):
    separator = "\t" if ptm_file_path.lower().endswith((".tsv")) else ","
    output_file = ptm_file_path + "_remapped.csv"
    # open the file in the write mode
    output = open(output_file, "w")
    # create the csv writer
    writer = csv.writer(output)

    idx_protein_id = -1
    idx_peptide_id = -1
    already_mapped = {}
    with open(ptm_file_path) as fd:
        rd = csv.reader(fd, delimiter=separator, quotechar='"')
        cnt = 0
        for row in rd:
            if cnt == 0:
                print(row)
                # it is header
                if ptm_file_id_column in row:
                    idx_protein_id = row.index(ptm_file_id_column)
                else:
                    raise Exception(
                        ptm_file_id_column + " not in file header of " + ptm_file_path
                    )
                if ptm_file_peptide_column in row:
                    idx_peptide_id = row.index(ptm_file_peptide_column)
                else:
                    raise Exception(
                        ptm_file_peptide_column
                        + " not in file header of "
                        + ptm_file_path
                    )
                cnt += 1
                # write a row to the csv file
                writer.writerow(row + ["remapped_protein"])
                continue

            protein = row[idx_protein_id]
            peptide = row[idx_peptide_id]
            # clean the peptide sequence because byonic sequence will contain ;
            clean_seq = peptide.split(";")[0]
            parts = clean_seq.split(".")
            prefix = ""
            suffix = ""
            pep = parts[0]
            if len(parts) == 3:
                prefix = parts[0]
                suffix = parts[2]
                pep = parts[1]

            # this avoided enzyme problem, but may cause problem is pre/sufix diffs
            clean_peptide = re.sub("[^A-Z]+", "", clean_seq.upper())
            # print(clean_peptide + "\n")

            if clean_peptide not in already_mapped:
                # add any condition here???
                new_protein_gene = remap_peptide(
                    clean_peptide, protein_ranks, fasta_subset
                )
                already_mapped[clean_peptide] = new_protein_gene
            writer.writerow(row + [already_mapped[clean_peptide]])
            cnt += 1

    # close the file
    output.close()


# use A2 as benchmark
# "HexNAc(3)Hex(6)NeuAc(1)"
glycan_rt = [
    ["", "HexNAc(3)Hex(3)", 10.13],
    ["", "HexNAc(3)Hex(3)Fuc(1)", 12.04],
    ["A2G0", "HexNAc(4)Hex(3)", 12.41],
    ["A1G1", "HexNAc(3)Hex(4)", 14.12],
    ["", "HexNAc(4)Hex(3)Fuc(1)", 14.48],
    ["M5", "HexNAc(2)Hex(5)", 15.51],
    ["A2G1F", "HexNAc(3)Hex(4)Fuc(1)", 16.25],
    ["", "HexNAc(4)Hex(4)", 16.65],
    ["A1G0M5", "HexNAc(3)Hex(5)", 17.88],
    ##["", "HexNAc(3)Hex(4)NeuAc(1)",    18.69   ],
    ["", "HexNAc(4)Hex(4)Fuc(1)", 18.69],
    ["", "HexNAc(2)Hex(6)", 19.69],
    ["", "HexNAc(4)Hex(5)", 20.39],
    ##["", "HexNAc(3)Hex(4)NeuAc(1)Fuc(1)",    20.87   ],
    # ["", "",    21.32   ],
    ["", "HexNAc(4)Hex(5)Fuc(1)", 22.24],
    ##["", "HexNAc(4)Hex(4)NeuAc(1)Fuc(1)",    22.78   ],
    ["", "HexNAc(2)Hex(7)", 23.87],
    ##["", "HexNAc(4)Hex(5)NeuAc(1)",    24.31   ],
    ##["", "HexNAc(4)Hex(5)NeuAc(1)Fuc(1)",    25.98   ],
    # ["", "",    27.07*  ],
    ["", "HexNAc(2)Hex(8)", 27.6],
    ##["", "HexNAc(4)Hex(5)NeuAc(2)",    28.27   ],
    ["", "HexNAc(5)Hex(6)Fuc(1)", 28.27],
    ##["", "HexNAc(4)Hex(5)NeuAc(2)Fuc(1)",    29.45   ],
    ["", "HexNAc(2)Hex(9)", 30.47]
    ##["", "HexNAc(5)Hex(5)NeuAc(1)Fuc(1)",    31.14   ],
    ##["", "HexNAc(5)Hex(6)NeuAc(2)Fuc(1)",    33.69   ],
    ##["", "HexNAc(5)Hex(6)NeuAc(3)Fuc(1)",    36.55   ],
    ##["", "HexNAc(6)Hex(7)NeuAc(2)Fuc(1)",    37.37   ],
    ##["", "HexNAc(6)Hex(7)NeuAc(3)Fuc(1)",    39.67   ],
    ##["", "HexNAc(6)Hex(7)NeuAc(4)Fuc(1)",    41.84   ]
]


def main(parameterList):
    glycan = Glycans()
    for tmps in glycan_rt:
        print(
            glycan_name_old_to_new(tmps[1], glycan.comp_to_name_dict)
            + "  "
            + str(tmps[1])
            + " "
            + str(tmps[2])
        )

    """
    train_glycan = [
        ["A2", 12.083],
        ["A2G1", 13.067],
        ["A2G1",     13.318],
        ["F1A2",     12.716],
        ["A2F1G1",  13.704],
        ["A2F1G1",   13.951],
        ["A2G2",     13.939],
        ["A3G1",     13.381],
        ["A3G1",     13.427],
        ["F1A3G1",   13.435],
        ["F1A3G1",   14.13],
        ["F1A3G1",   14.13],
        ["A3G2",     14.47]
    ]
    """
    train_glycan = [
        ["HexNAc(3)Hex(3)", 10.13],
        ["HexNAc(3)Hex(3)Fuc(1)", 12.04],
        ["HexNAc(4)Hex(3)", 12.41],
        ["HexNAc(3)Hex(4)", 14.12],
        ["HexNAc(4)Hex(3)Fuc(1)", 14.48],
        ["HexNAc(2)Hex(5)", 15.51],
        ["HexNAc(3)Hex(4)Fuc(1)", 16.25],
        ["HexNAc(5)Hex(5)NeuAc(1)", 100],
    ]

    # protein_file_path = parameterList[1]

    """
    Glycan structure    Peptide Predicted RT, GU    Exp RT, GU  Difference, GU  Difference, s
    A2  IgG1    13.271  13.686  0.415   47
    F1A2    IgG1    14.367  14.378  0.011   1
    A2G1    IgG1    14.458  14.545  0.087   10
    A2G1    IgG1    14.458  14.799  0.341   38
    F1A2G1  IgG1    15.186  15.265  0.079   10
    F1A2G1  IgG1    15.186  15.475  −0.124  −14
    A2G2    IgG1    15.645  15.615  −0.030  −3
    F1A2G2  IgG1    16.005  16.334  −0.039  −4

    F1A2    IgG2    13.293  13.183  −0.110  −12
    F1A2G1  IgG2    14.112  14.020  −0.092  −10
    F1A2G1  IgG2    14.112  14.229  0.117   13
    F1A2G2  IgG2    14.931  15.068  0.137   16
    F1A2    IgG3    13.830  13.760  −0.070  −8
    F1A2G2  IgG3    15.468  15.683  −0.153  −17



    rt_shift_dict = {
        "Fuc":  0.692  , #14.378-13.686
        "F":  0.692  , 
        "G":  0.859, #1.113]         , # Gal. 14.545-13.686

        "Hex": 1
    }

    rabbit igg
    Glycan structure    Predicted RT, GU    Exp RT, GU  Difference, GU  Difference, s
    A2  12.032  12.083  0.051   6
    A2G1    13.009  13.067  0.058   7
    A2G1    13.219  13.318  0.099   11
    F1A2    13.218  12.716  −0.412  −47
    A2F1G1  13.737  13.704  −0.033  −4
    A2F1G1  13.947  13.951  0.004   1
    A2G2    14.038  13.939  −0.099  −11
    A3G1    13.060  13.381  0.321   36
    A3G1    13.260  13.427  0.167   19
    F1A3G1  13.979  13.435  −0.544  −62
    F1A3G1  14.147  14.130  −0.065  −7
    F1A3G1  14.357  14.130  −0.277  −26
    A3G2    14.438  14.470  0.032   4
    
    rt_shift_dict = {
        "Fuc":  0.633  , #14.378-13.686
        "F":  0.633  , 
        "G":  0.984, #1.235]         , # Gal. 14.545-13.686


        "Hex":  1,
        "M":2,
        "S":3,
        "Sg": 4
    }
    """

    predicted_rts = []
    for name, rt in train_glycan:
        predicted_rts.append([name, get_predicted_rt_from_comp(name)])

    print(predicted_rts)

    # spearman correlation

    correlation, p_value = spearmanr(
        [a[1] for a in predicted_rts], [a[1] for a in train_glycan]
    )
    print(correlation, p_value)


def get_amgen_glycan_comp(name: str) -> dict:
    import collections

    name = name.split(" ")[0]
    result = collections.defaultdict(int)
    if "(" not in name:
        # amgen name
        i = 0
        comp = ""
        cnt = ""
        while i < len(name):
            if name[i] in "AGFSM":
                comp = name[i]
                cnt = ""
                if name[i] == "S" and i + 1 < len(name) and name[i + 1] == "g":
                    i = i + 1
                    comp = "Sg"
                while i + 1 < len(name) and name[i + 1].isnumeric():
                    cnt = cnt + name[i + 1]
                    i += 1
                result[comp] = 1 if cnt == "" else int(cnt)
                i += 1
            else:
                raise Exception("wrong format")
        return result


def get_predicted_rt(name: str) -> float:
    # 216_2023_4533_MOESM2_ESM.xlsx
    # not used
    # Table 6" https://www.tandfonline.com/doi/full/10.1080/19420862.2018.1436921#d1e250
    # https://data.nist.gov/od/id/mds2-2497
    rt_shift_dict = {
        "Fuc": 0.633,  # 14.378-13.686
        "F": 0.633,
        "G": 0.984,  # 1.235]         , # Gal. 14.545-13.686
        "A": 0,
        "Hex": 1,
        "M": 2,
        "S": 3,
        "Sg": 4,
    }

    comps = get_amgen_glycan_comp(name)
    # base case is A2
    score = 0
    for comp, cnt in comps.items():
        base_cnt = 0
        if comp == "A":
            base_cnt = 2
        diff = cnt - base_cnt

        score += rt_shift_dict[comp] * diff

    return score


# 5 counts:
# HexNAc(4)Hex(5)Fuc(1)NeuAc(1)NeuGc(1)


def get_predicted_rt_from_comp(compositionName: str) -> float:
    comp_list = ["HexNAc", "Hex", "Fuc", "NeuAc", "NeuGc"]
    # "NeuAc","NeuGc" seems elute late in reverse phase?
    comp_list_score = [2.3, 3.9, 1.95, -14.57, -14.57]

    # 216_2023_4533_MOESM2_ESM.xlsx
    # not used
    # Table 6" https://www.tandfonline.com/doi/full/10.1080/19420862.2018.1436921#d1e250
    # https://data.nist.gov/od/id/mds2-2497
    rt_shift_dict = {
        "HexNAc": 2.3,
        "Fuc": 1.95,
        "Hex": 3.9,
        "NeuAc": 4.57,
        "NeuGc": 4.57,
    }
    # print("get_predicted_rt_from_comp " + compositionName)
    glycan = Glycans()

    new_name = glycan_name_old_to_new(compositionName, glycan.comp_to_name_dict)
    # print(new_name)

    # glycan name to
    name_to_rt = {}
    comp_to_rt = {}
    comp_list_to_rt = {}
    for n, c, t in glycan_rt:
        if n == "":
            n = glycan_name_old_to_new(c, glycan.comp_to_name_dict)
        # glycan_rt_new.append([n, c, t])
        # print(glycan_rt_new[-1])
        name_to_rt[n] = t
        comp_to_rt[c] = t
        comp_list_to_rt[tuple(get_glycan_composition_list(c))] = t
    # print(comp_list_to_rt)

    # print(name_to_rt)
    # print(comp_to_rt)
    if "/" in new_name:
        # e.g. A1G1/A1G0M4
        new_name = new_name.split("/")[0]
    if new_name in name_to_rt:
        return name_to_rt[new_name]
    if compositionName in comp_to_rt:
        return comp_to_rt[compositionName]

    # evaluate diff
    def evaluate_diff(compositionName, predicted_rt):
        current_comp = get_glycan_composition_list(compositionName)
        conflict = 0
        for k, v in comp_list_to_rt.items():
            dist = 0
            diff = []
            score = 0
            for i in range(len(current_comp)):
                dist += abs(current_comp[i] - k[i])
                score += (current_comp[i] - k[i]) * comp_list_score[i]
            if dist <= 2:
                if score * (predicted_rt - v) < 0:
                    # shift to different direction
                    conflict += 1
        return conflict

    # get distance
    current_comp = get_glycan_composition_list(compositionName)
    min_dist = float("inf")
    min_dist_comp = []
    min_dist_comp_diff = []
    min_dist_comp_score = []
    for k, v in comp_list_to_rt.items():
        dist = 0
        diff = []
        score = v
        for i in range(len(current_comp)):
            dist += abs(current_comp[i] - k[i])
            score += (current_comp[i] - k[i]) * comp_list_score[i]
            if abs(current_comp[i] - k[i]) > 0:
                diff.append(str(current_comp[i] - k[i]) + "x" + comp_list[i])
        if dist < min_dist:
            min_dist = dist
            min_dist_comp = [[k, v]]
            min_dist_comp_diff = [diff]
            min_dist_comp_score = [score]
        elif dist == min_dist:
            min_dist_comp.append([k, v])
            min_dist_comp_diff.append(diff)
            min_dist_comp_score.append(score)
    if debug == True:
        print("min distance of " + compositionName + "is :" + str(min_dist))
        print(min_dist_comp)
        print(min_dist_comp_diff)
        print(min_dist_comp_score)

    current_min_idx = 0
    if len(min_dist_comp_score) > 1:
        current_min = float("inf")

        for i in range(len(min_dist_comp_score)):
            conflicts = evaluate_diff(compositionName, min_dist_comp_score[i])
            if debug:
                print(
                    "Reevluating conflits: "
                    + str(min_dist_comp_score[i])
                    + " is "
                    + str(conflicts)
                )
            if conflicts < current_min:
                current_min = conflicts
                current_min_idx = i
    return min_dist_comp_score[current_min_idx]


def get_key(row):
    # add modification info
    k = (
        str(row.get("Sequence", ""))
        + "?"
        + str(row.get("Protein---Position---Gene", ""))
    )
    mod_str = str(row.get("Modifications", ""))
    mod_str_without_glycan = []
    if ";" in mod_str:
        tmp = mod_str.split(";")
        for t in tmp:
            if "Hex" not in t:
                mod_str_without_glycan.append(t.strip())
    if len(mod_str_without_glycan) > 0:
        k += "?" + ";".join(sorted(mod_str_without_glycan))

    return k


def _has_glycan_name(val) -> bool:
    """Check if a Converted Glycan Names value is non-empty (handles NaN)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return len(str(val)) > 0


def site_unique_ids_counter(df):
    site_to_glycan_list = defaultdict(set)
    for index, row in df.iterrows():
        if _has_glycan_name(row["Converted Glycan Names"]):
            site_to_glycan_list[get_key(row)].add(row["Converted Glycan Names"])
    return site_to_glycan_list


def site_unique_ids_counter_with_rt(df, rt_column=""):
    if not rt_column or rt_column not in df.columns:
        return {}
    site_to_glycan_list_with_rt = defaultdict(list)
    for index, row in df.iterrows():
        if _has_glycan_name(row["Converted Glycan Names"]):
            comp = row["Glycan Composition"]
            if ";" in comp:
                comp = comp.split(";")[0]
            rt = row[rt_column]
            site_to_glycan_list_with_rt[get_key(row)].append(
                [comp, rt, "", float("-inf")]
            )
    return site_to_glycan_list_with_rt


def absent_correlation_score(ls: list):
    # each list item name, exp_rt, theroy_rt, corr_score
    # last corr_score is not used here
    # v is list [['HexNAc(2)Hex(5)', 49.47,""], ['HexNAc(2)Hex(8)', 48.67,""]]

    # spearman correlation

    correlation, p_value = spearmanr(
        [a[2] for a in ls], [a[1] for a in ls]  # predicted rt  # exp rt
    )
    print(correlation, p_value)


import pandas as pd
import collections as _collections_std


def compute_composite_validation_score(
    df: pd.DataFrame,
    depth_col: str = "depth",
    rt_conflict_col: str = "rt_conflics",
    byonic_col_prefix: str = "Byonic Score (",
    w_depth: float = 0.4,
    w_conflict: float = 0.4,
    w_byonic: float = 0.2,
) -> pd.DataFrame:
    """Compute a rank-percentile composite validation score.

    Lower depth and rt_conflict are better; higher Byonic Score is better.
    Each metric is converted to a rank-percentile in [0, 1] (higher = better),
    then combined as a weighted sum.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: depth_pct, rt_conflict_pct, engine_score_pct,
        composite_validation_score.
    """
    # Find the Byonic Score column
    byonic_cols = [c for c in df.columns if c.startswith(byonic_col_prefix)]
    byonic_col = byonic_cols[0] if byonic_cols else None

    n = len(df)
    composite = pd.Series([""] * n, index=df.index)
    depth_pct_out = pd.Series([""] * n, index=df.index)
    conflict_pct_out = pd.Series([""] * n, index=df.index)
    engine_pct_out = pd.Series([""] * n, index=df.index)

    # Convert depth to numeric (lower = better → invert percentile)
    depth_numeric = pd.to_numeric(df[depth_col], errors="coerce")
    # Convert rt_conflict to numeric (lower = better → invert percentile)
    conflict_numeric = pd.to_numeric(df[rt_conflict_col], errors="coerce")
    # Byonic score (higher = better → direct percentile)
    byonic_numeric = (
        pd.to_numeric(df[byonic_col], errors="coerce") if byonic_col else None
    )

    depth_pct = depth_numeric.rank(method="average", ascending=True, na_option="keep")
    depth_count = depth_numeric.notna().sum()
    if depth_count > 0:
        depth_pct = 1.0 - (depth_pct - 1) / max(depth_count - 1, 1)

    conflict_pct = conflict_numeric.rank(
        method="average", ascending=True, na_option="keep"
    )
    conflict_count = conflict_numeric.notna().sum()
    if conflict_count > 0:
        conflict_pct = 1.0 - (conflict_pct - 1) / max(conflict_count - 1, 1)

    if byonic_numeric is not None:
        byonic_pct = byonic_numeric.rank(
            method="average", ascending=True, na_option="keep"
        )
        byonic_count = byonic_numeric.notna().sum()
        if byonic_count > 0:
            byonic_pct = (byonic_pct - 1) / max(byonic_count - 1, 1)
    else:
        byonic_pct = pd.Series([float("nan")] * n, index=df.index)

    # Only compute for rows that have a glycan name (non-empty depth)
    has_data = depth_numeric.notna()

    for idx in df.index:
        if not has_data.loc[idx]:
            continue
        d = depth_pct.loc[idx] if pd.notna(depth_pct.loc[idx]) else 0.5
        c = conflict_pct.loc[idx] if pd.notna(conflict_pct.loc[idx]) else 0.5
        b = byonic_pct.loc[idx] if pd.notna(byonic_pct.loc[idx]) else 0.5

        depth_pct_out.loc[idx] = format(d, ".4f")
        conflict_pct_out.loc[idx] = format(c, ".4f")
        engine_pct_out.loc[idx] = format(b, ".4f")

        # Re-normalize weights if Byonic is unavailable
        if byonic_col is None:
            comp = (d + c) / 2.0
        else:
            comp = w_depth * d + w_conflict * c + w_byonic * b

        composite.loc[idx] = format(comp, ".4f")

    return pd.DataFrame(
        {
            "depth_pct": depth_pct_out,
            "rt_conflict_pct": conflict_pct_out,
            "engine_score_pct": engine_pct_out,
            "composite_validation_score": composite,
        },
        index=df.index,
    )


def validate_glycans(
    input_csv: str,
    output_csv: str = "output.csv",
    abd_prefix: str = "Abundances (Grouped): ",
    w_depth: float = 0.4,
    w_conflict: float = 0.4,
    w_byonic: float = 0.2,
    rt_column: str = "",
) -> str:
    """Read a results CSV, add depth/predicted-RT/conflict columns, and save.

    Parameters
    ----------
    input_csv : str
        Path to the input CSV file (e.g. ``*_results_unfiltered.csv``).
    output_csv : str, optional
        Path for the output CSV.  Defaults to ``"output.csv"``.

    Returns
    -------
    str
        The *output_csv* path that was written.
    """

    df = pd.read_csv(input_csv)
    counter = _collections_std.Counter(df["Converted Glycan Names"])
    results = sorted(counter.items(), key=lambda x: x[1], reverse=True)

    # create an abundance-based counter rank for glycans
    abd_cols = [c for c in df.columns if c.startswith(abd_prefix)]
    abundance_counter = {}
    if abd_cols:
        for name, group in df.groupby("Converted Glycan Names"):
            if _has_glycan_name(name):
                abundance_counter[name] = group[abd_cols].sum().sum()
    abundance_results = sorted(
        abundance_counter.items(), key=lambda x: x[1], reverse=True
    )

    counter_rank = {}
    for i, (name, _cnt) in enumerate(results):
        counter_rank[name] = i + 1
    print("glycan ranking based on counts:")
    print(results)

    abundance_counter_rank = {}
    for i, (name, _cnt) in enumerate(abundance_results):
        abundance_counter_rank[name] = i + 1
    print("glycan ranking based on abundance:")
    print(abundance_results)

    # unique glycan IDs per site
    site_to_glycan_list = site_unique_ids_counter(df)

    # depth column
    depth_column = []
    for _index, row in df.iterrows():
        if _has_glycan_name(row["Converted Glycan Names"]):
            glycan_name = row["Converted Glycan Names"]
            glycan_list = site_to_glycan_list[get_key(row)]
            length = len(glycan_list)
            global_glycan_ranking = min(
                counter_rank[glycan_name], abundance_counter_rank[glycan_name]
            )
            depth_column.append(format(global_glycan_ranking * 1.0 / length, ".2f"))
        else:
            depth_column.append("")
    df2 = df.assign(depth=depth_column)

    # predicted RT and conflict score
    rt_counter = site_unique_ids_counter_with_rt(df, rt_column=rt_column)
    for k, v in rt_counter.items():
        for i in range(len(v)):
            gly = v[i][0]
            # NOTE: must multiply by -1
            rt_counter[k][i][2] = -1 * get_predicted_rt_from_comp(gly)

        for i in range(len(v)):
            _gly, exp_rt, pred_rt, _ = v[i]
            conf = 0
            for j in range(len(v)):
                if j == i:
                    continue
                _gly_j, exp_rt_j, pred_rt_j, _ = v[j]
                if (float(exp_rt_j) - float(exp_rt)) * (
                    float(pred_rt_j) - float(pred_rt)
                ) < 0:
                    conf += 1
            if len(v) <= 1:
                rt_counter[k][i][3] = "NA"
            else:
                rt_counter[k][i][3] = format(conf * 1.0 / len(v), ".2f")

    prt_column = []
    conf_column = []
    id_column = []
    for _index, row in df2.iterrows():
        if _has_glycan_name(row["Converted Glycan Names"]):
            glycan_list = rt_counter[get_key(row)]
            prt_column.append(glycan_list[0][2])
            conf_column.append(glycan_list[0][3])
            id_column.append(get_key(row))
            rt_counter[get_key(row)].pop(0)
        else:
            prt_column.append("")
            conf_column.append("")
            id_column.append("")

    df2 = df2.assign(full_id=id_column)
    df2 = df2.assign(predicte_rt=prt_column)
    df2 = df2.assign(rt_conflics=conf_column)

    # Compute composite validation score and percentile columns
    score_df = compute_composite_validation_score(
        df2,
        w_depth=w_depth,
        w_conflict=w_conflict,
        w_byonic=w_byonic,
    )
    df2 = df2.assign(
        depth_pct=score_df["depth_pct"],
        rt_conflict_pct=score_df["rt_conflict_pct"],
        engine_score_pct=score_df["engine_score_pct"],
        composite_validation_score=score_df["composite_validation_score"],
    )

    df2.to_csv(output_csv, index=False)
    return output_csv


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2:
        in_file = sys.argv[1]
        out_file = sys.argv[2] if len(sys.argv) >= 3 else "output.csv"
    else:
        in_file = "glycan_validator_test/pd_peptide_group_export_20191003_DCX_mouse_plasma_intact_HCD_ordered_o_y_RT5min_1605036722_results_unfiltered.csv"
        out_file = "glycan_validator_test/output_test.csv"

    validate_glycans(in_file, out_file)
    print("finished")


'''
from gpt chat
from scipy.stats import kendalltau

def score_elements(true_rank, unknown_rank):
    """
    Determine the score of each element in the unknown rank indicating whether the element improves the overall rank.

    Parameters:
    true_rank (list): The true rank list.
    unknown_rank (list): The unknown rank list.

    Returns:
    dict: A dictionary with elements of unknown_rank as keys and their scores as values.
    """
    initial_tau, _ = kendalltau(true_rank, unknown_rank)
    scores = {}

    for i in range(len(unknown_rank)):
        modified_rank = unknown_rank[:i] + unknown_rank[i+1:]
        tau, _ = kendalltau(true_rank, modified_rank)
        scores[unknown_rank[i]] = tau - initial_tau

    return scores

# Example usage
true_rank = [1, 2, 3, 4, 5]
unknown_rank = [5, 3, 4, 1, 2]
scores = score_elements(true_rank, unknown_rank)
print("Scores:", scores)
'''
