#!/usr/bin/env python

import os
import re
import sys
import json
import pytz
import numpy
import shutil
import string
import logging
import zipfile
import datetime
from glob import glob
from pprint import pprint as pp
from nibabel import parrec
import classification_from_label

logging.basicConfig()
log = logging.getLogger('parrec-mr-classifier')

def assign_type(s):
    """
    Sets the type of a given input.
    """
    if type(s) == list or type(s) == numpy.ndarray:
        try:
            return [ int(x) for x in s ]
        except ValueError:
            try:
                return [ float(x) for x in s ]
            except ValueError:
                return [ format_string(x) for x in s if len(x) > 0 ]
    else:
        s = str(s)
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return format_string(s)


def format_string(in_string):
    """
    Sanitize strings for input in the DB.
    """
    # Remove non-ascii characters
    formatted = re.sub(r'[^\x00-\x7f]',r'', str(in_string)) # Remove non-ascii characters
    formatted = filter(lambda x: x in string.printable, formatted)
    if len(formatted) == 1 and formatted == '?':
        formatted = None
    return formatted


def parrec_classify(input_file_path, output_dir, timezone):
    """
    Extract metadata from PAR file header (even within a zip file) and write
    info fields to .metadata.json.
    """
    par_file = ''
    rec_file = ''
    # If zip file load zip and get a list of files within the archive
    if zipfile.is_zipfile(input_file_path):
        par_zip = zipfile.ZipFile(input_file_path)
        files_in_zip = par_zip.namelist()

        # Extract files to tmp
        for f in files_in_zip:
            if f.lower().endswith('.par'):
                par_file = os.path.join('/tmp/', f)
                # Need to have both PAR and REC files
                par_zip.extractall('/tmp')
                if os.path.isfile(par_file):
                    break
    else:
        par_file = input_file_path
        # There could also be a REC file in the input directory
        # rec_dir = '/flywheel/v0/input/rec'
        rec_file = glob('/flywheel/v0/input/rec/*REC')
        if len(rec_file) == 1 and os.path.isfile(rec_file[0]):
            shutil.copyfile(rec_file[0], os.path.join(os.path.dirname(par_file), os.path.basename(rec_file[0])))
            rec_file = glob(os.path.join(os.path.dirname(par_file), '*REC'))
        else:
            log.warning('No REC corresponding REC file could be found! Attempting to continue!')
            shutil.copyfile(par_file, par_file.replace('PAR', 'REC'))

    # Load the par file and parse the header
    if par_file:
        try:
            par = parrec.load(par_file, permit_truncated=True)
            par_file_header = par.get_header()
            par_header_info = par_file_header.general_info
        except:
            log.error('Failed to load ' + os.path.basename(par_file))
            sys.exit(1)
    else:
        log.error('No PAR file was found in the archive.')
        sys.exit(1)

    # Extract the header values and sanitize for entry
    header = {}

    # Allowed types
    types = [list, float, int, str]
    for k,v in par_header_info.iteritems():
        value = assign_type(v)
        if value and type(value) in types:
            # Put the value in the header
            header[k] = value
        else:
            log.debug('Excluding ' + k)
    log.info('done')


    ###########################################################################
    # Build metadata
    metadata = {}

    # Session metadata
    metadata['session'] = {}
    metadata['session']['timestamp'] = pytz.timezone(args.timezone).localize(datetime.datetime.strptime(par_header_info['exam_date'], '%Y.%m.%d / %H:%M:%S')).isoformat()

    # Subject Metadata
    metadata['session']['subject'] = {}
    full_name = par_header_info['patient_name']
    firstname = full_name.split(' ')[0]
    lastname = full_name.split(firstname)[1]
    if firstname:
        metadata['session']['subject']['firstname'] = firstname
    if lastname:
        metadata['session']['subject']['lastname'] = lastname

    # Acquisition metadata
    metadata['acquisition'] = {}
    metadata['acquisition']['instrument'] = 'MR'
    metadata['acquisition']['label'] = par_header_info['protocol_name']
    metadata['acquisition']['timestamp'] = pytz.timezone(args.timezone).localize(datetime.datetime.strptime(par_header_info['exam_date'], '%Y.%m.%d / %H:%M:%S')).isoformat()

    # File metadata
    parrec_file = {}
    parrec_file['name'] = os.path.basename(input_file_path)
    parrec_file['modality'] = 'MR'
    parrec_file['classification'] = classification_from_label.infer_classification(par_header_info['protocol_name'])
    parrec_file['info'] = {}

    # File metadata extracted from PAR file header
    if header:
        parrec_file['info'] = header
        # Check for diffusion measurement
        if header.has_key('diffusion') and header['diffusion']:
            log.info('Detected diffusion data - overriding.')
            parrec_file['classification'] = {'Intent': ['Structural'],
                               'Measurement': ['Diffusion']}

    # Append the parrec_file to the files array
    metadata['acquisition']['files'] = []
    metadata['acquisition']['files'].append(parrec_file)

    # If there was a REC file, also update info for that file
    # NOTE - We *could* assume that there is a REC file next to the PAR file in
    # the DB and attempt to set the info for that file as well.
    # NOTE that we do not do this now.
    if rec_file and os.path.isfile(rec_file[0]):
        rec_file_info = parrec_file.copy()
        rec_file_info['name'] = os.path.basename(rec_file[0])
        metadata['acquisition']['files'].append(rec_file_info)
        os.remove(rec_file[0])

    # Write out the metadata to file (.metadata.json)
    metafile_outname = os.path.join(output_dir,'.metadata.json')
    with open(metafile_outname, 'w') as metafile:
        json.dump(metadata, metafile)
    pp(metadata)
    return metafile_outname


if __name__ == '__main__':
    """
    Generate session, subject, and acquisition metatada by parsing the PAR/REC file
    header, using nibabel.
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('parrec_input_file', help='path to par file or parrec zip')
    ap.add_argument('output_dir', default= '/flywheel/v0/output', help='output directory')
    ap.add_argument('--log_level', help='logging level', default='info')
    ap.add_argument('-z', '--timezone', help='instrument timezone [system timezone]', default='UTC')
    args = ap.parse_args()

    log.setLevel(getattr(logging, args.log_level.upper()))
    logging.getLogger('parrec-mr-classifier').setLevel(logging.INFO)
    log.info('start: %s' % datetime.datetime.utcnow())

    metadatafile = parrec_classify(args.parrec_input_file, args.output_dir, args.timezone)

    if os.path.exists(metadatafile):
        log.info('generated %s' % metadatafile)
    else:
        log.info('failure! %s was not generated!' % metadatafile)

    log.info('stop: %s' % datetime.datetime.utcnow())
