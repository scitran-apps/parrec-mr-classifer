#!/usr/bin/env python

import os
import re
import sys
import json
import string
import logging
import zipfile
import datetime
from nibabel import parrec
import measurement_from_label

logging.basicConfig()
log = logging.getLogger('parrec-mr-classifier')


def parrec_classify(zip_file_path, output_dir, timezone):
    """
    Extract metadata from PAR file header (within a zip file) and write general
    info fields to .metadata.json.
    """
    # Load zip and get a list of files within the archive
    par_zip = zipfile.ZipFile(zip_file_path)
    files_in_zip = par_zip.namelist()

    # Extract files to tmp
    for f in files_in_zip:
        if f.lower().endswith('.par'):
            par_file = os.path.join('/tmp/', f)
            # Need to have both PAR and REC files
            par_zip.extractall('/tmp')
            if os.path.isfile(par_file):
                break

    # Load the par file and parse the header
    if par_file:
        try:
            par = parrec.load(par_file)
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
    types = [list, float, int]
    for k,v in par_header_info.iteritems():
        value = assign_type(v)
        if value and type(value) in types:
            # Put the value in the header
            header[k] = value
        else:
            log.debug('Excluding ' + k)
    log.info('done')

    # Build metadata
    metadata = {}

    # Session metadata
    metadata['session'] = {}
    metadata['session']['timestamp'] = datetime.datetime.strptime(par_header_info['exam_date'], '%Y.%m.%d / %H:%M:%S').isoformat()

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
    metadata['acquisition']['measurement'] = measurement_from_label.infer_measurement(par_header_info['protocol_name'])

    # Set to the study exam date
    metadata['acquisition']['timestamp'] = datetime.datetime.strptime(par_header_info['exam_date'], '%Y.%m.%d / %H:%M:%S').isoformat()

    # Acquisition metadata extracted from PAR file header
    if header:
        metadata['acquisition']['metadata'] = {}
        metadata['acquisition']['metadata'] = header

    # Write out the metadata to file (.metadata.json)
    metafile_outname = os.path.join(output_dir,'.metadata.json')
    with open(metafile_outname, 'w') as metafile:
        json.dump(metadata, metafile)

    return metafile_outname


def assign_type(s):
    """
    Set the type of a given input of unknown type to a sane type.
    """
    if type(s) == list:
        return s
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
    formatted = re.sub(r'[^\x00-\x7f]',r'', str(in_string))
    formatted = filter(lambda x: x in string.printable, formatted)
    if len(formatted) == 1 and formatted == '?':
        formatted = None
    return formatted


if __name__ == '__main__':
    """
    Generate session, subject, and acquisition metatada by parsing the PAR file
    header, using nibabel.
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('parrec_input_zipfile', help='path to par/rec zip')
    ap.add_argument('output_dir', default= '/flywheel/v0/output', help='output directory')
    ap.add_argument('--log_level', help='logging level', default='info')
    ap.add_argument('-z', '--timezone', help='instrument timezone [system timezone]', default=None)
    args = ap.parse_args()

    log.setLevel(getattr(logging, args.log_level.upper()))
    logging.getLogger('parrec-mr-classifier').setLevel(logging.INFO)
    log.info('start: %s' % datetime.datetime.utcnow())

    metadatafile = parrec_classify(args.parrec_input_zipfile, args.output_dir, args.timezone)

    if os.path.exists(metadatafile):
        log.info('generated %s' % metadatafile)
    else:
        log.info('failure! %s was not generated!' % metadatafile)

    log.info('stop: %s' % datetime.datetime.utcnow())
