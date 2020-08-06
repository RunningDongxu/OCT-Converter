import numpy as np
from construct import PaddedString, Int16un, Struct, Int32sn, Int32un, Array, Int8un
from oct_converter.image_types import OCTVolumeWithMetaData, FundusImageWithMetaData
import struct
import matplotlib.pyplot as plt
import setup_logger


class E2E(object):
    """ Class for extracting data from Heidelberg's .e2e file format.

        Notes:
            Mostly based on description of .e2e file format here:
            https://bitbucket.org/uocte/uocte/wiki/Heidelberg%20File%20Format.

        Attributes:
            filepath (str): Path to .img file for reading.
            header_structure (obj:Struct): Defines structure of volume's header.
            main_directory_structure (obj:Struct): Defines structure of volume's main directory.
            sub_directory_structure (obj:Struct): Defines structure of each sub directory in the volume.
            chunk_structure (obj:Struct): Defines structure of each data chunk.
            image_structure (obj:Struct): Defines structure of image header.
    """


    def __init__(self, filepath, imagetype=""):
        self.filepath = filepath
        self.logger = setup_logger.get_logger()#('extract_e2e.log')
        self.imagetype = imagetype
        self.laterality = None
        self.header_structure = Struct(
            'magic' / PaddedString(12, 'ascii'),
            'version' / Int32un,
            'unknown' / Array(10, Int16un)
        )
        self.main_directory_structure = Struct(
            'magic' / PaddedString(12, 'ascii'),
            'version' / Int32un,
            'unknown' / Array(10, Int16un),
            'num_entries' / Int32un,
            'current' / Int32un,
            'prev' / Int32un,
            'unknown3' / Int32un,
        )
        self.sub_directory_structure = Struct(
            'pos' / Int32un,
            'start' / Int32un,
            'size' / Int32un,
            'unknown' / Int32un,
            'patient_id' / Int32un,
            'study_id' / Int32un,
            'series_id' / Int32un,
            'slice_id' / Int32sn,
            'unknown2' / Int16un,
            'unknown3' / Int16un,
            'type' / Int32un,
            'unknown4' / Int32un,
        )
        self.chunk_structure = Struct(
            'magic' / PaddedString(12, 'ascii'),
            'unknown' / Int32un,
            'unknown2' / Int32un,
            'pos' / Int32un,
            'size' / Int32un,
            'unknown3' / Int32un,
            'patient_id' / Int32un,
            'study_id' / Int32un,
            'series_id' / Int32un,
            'slice_id' / Int32sn,
            'ind' / Int16un,
            'unknown4' / Int16un,
            'type' / Int32un,
            'unknown5' / Int32un,
        )
        self.patient_info_structure = Struct(
            'name' / PaddedString(31, 'ascii'),
            'surname' / PaddedString(66, 'ascii'),
            'birthdate' / Int32un,
            'sex' / Int8un
        )
        self.lat_structure = Struct(
            # 'unknown' / Int8un,
            # 'unknown' / PaddedString(14, 'ascii'),
            'unknown' / Array(14, Int16un),
            'laterality' / Int8un,
            'unknown2' / Int8un
        )
        self.image_structure = Struct(
            'size' / Int32un,
            'type' / Int32un,
            'unknown' / Int32un,
            'width' / Int32un,
            'height' / Int32un,
        )

    def read_oct_volume(self):
        """ Reads OCT data.

            Returns:
                obj:OCTVolumeWithMetaData
        """
        with open(self.filepath, 'rb') as f:
            raw = f.read(36)
            header = self.header_structure.parse(raw)

            raw = f.read(52)
            main_directory = self.main_directory_structure.parse(raw)

            # traverse list of main directories in first pass
            directory_stack = []

            current = main_directory.current
            while current != 0:
                directory_stack.append(current)
                f.seek(current)
                raw = f.read(52)
                directory_chunk = self.main_directory_structure.parse(raw)
                current = directory_chunk.prev

            # traverse in second pass and  get all subdirectories
            chunk_stack = []
            volume_dict = {}
            for position in directory_stack:
                f.seek(position)
                raw = f.read(52)
                directory_chunk = self.main_directory_structure.parse(raw)

                for ii in range(directory_chunk.num_entries):
                    raw = f.read(44)
                    chunk = self.sub_directory_structure.parse(raw)
                    if self.imagetype == "Fundus Autofluorescence":
                        if chunk.start > chunk.pos:
                            chunk_stack.append([chunk.start, chunk.size])
                    else:
                        volume_string = '{}_{}_{}'.format(chunk.patient_id, chunk.study_id, chunk.series_id)
                        if volume_string not in volume_dict.keys():
                            volume_dict[volume_string] = chunk.slice_id / 2
                        elif chunk.slice_id / 2 > volume_dict[volume_string]:
                                volume_dict[volume_string] = chunk.slice_id / 2
                        if chunk.start > chunk.pos:
                            chunk_stack.append([chunk.start, chunk.size])

            if self.imagetype == "Fundus Autofluorescence":
                for start, pos in chunk_stack:
                    f.seek(start)
                    raw = f.read(60)
                    chunk = self.chunk_structure.parse(raw)
                    volume_string = '{}_{}_{}'.format(chunk.patient_id, chunk.study_id, chunk.series_id)
                    if volume_string not in volume_dict.keys():
                        volume_dict[volume_string] = chunk.slice_id
                    elif chunk.slice_id / 2 > volume_dict[volume_string]:
                        volume_dict[volume_string] = chunk.slice_id

                # initalise dict to hold all the images
                volume_array_dict = {}
                for volume, num_slices in volume_dict.items():
                    if num_slices == 0:
                        num_slices = 1
                        volume_array_dict[volume] = [0] * int(num_slices)
                    elif num_slices >  0:
                        volume_array_dict[volume] = [0] * int(num_slices)
            else:
                # initalise dict to hold all the image volumes
                volume_array_dict = {}
                for volume, num_slices in volume_dict.items():
                    if num_slices > 0:
                        volume_array_dict[volume] = [0] * int(num_slices)
            # traverse all chunks and extract slices
            fundus_images = {}
            numfun = 0
            for start, pos in chunk_stack:
                f.seek(start)
                raw = f.read(60)
                chunk = self.chunk_structure.parse(raw)
                if self.imagetype == "Fundus Autofluorescence":
                    if chunk.type == 11: # laterality data
                        try:
                            raw = f.read(60)
                            laterality_data = self.lat_structure.parse(raw)
                            # laterality information is decimal encoded - convert to ASCII representation (http://www.asciitable.com/)
                            if laterality_data.laterality == 82:
                                self.laterality = 'R'
                            elif laterality_data.laterality == 76:
                                self.laterality = 'L'
                        except UnicodeDecodeError as ue:
                            self.logger.warning("cannot decode laterality, data structure differs from what is expected - passing")

                if chunk.type == 1073741824:  # image data
                    raw = f.read(20)
                    image_data = self.image_structure.parse(raw)

                    # hack for extracting laterality from oct vols
                    # first two fundus images are left eye, last two are right eye
                    if chunk.ind == 0:  # fundus data
                        # pass
                        height, width = (image_data.height, image_data.width)
                        try:
                            raw_volume = [struct.unpack('B', f.read(1))[0] for pixel in range(height*width)]
                            image = np.array(raw_volume).reshape(height,width)
                            if self.imagetype == "Fundus Autofluorescence":
                                # raw_volume = [struct.unpack('H', f.read(2))[0] for pixel in range(height*width)]
                                # plt.imshow(image, cmap='gray')
                                # plt.show()
                                fundus_images.append((self.laterality, image))
                            else:
                                volume_string = '{}_{}_{}'.format(chunk.patient_id, chunk.study_id, chunk.series_id)
                                if volume_string in volume_array_dict.keys():
                                    # print("faf volume string: ", volume_string)
                                    if numfun < 2:
                                        self.laterality = 'R'
                                    else:
                                        self.laterality = 'L'
                                    fundus_images[volume_string] = (self.laterality, image)
                                    numfun += 1
                        except Exception as e:
                            print("error {}".format(e))
                            return fundus_images
                        # volume_string = '{}_{}_{}'.format(chunk.patient_id, chunk.study_id, chunk.series_id)
                        # print("fundus volume string ", volume_string)
                        if volume_string in volume_array_dict.keys():
                            volume_array_dict[volume_string][int(chunk.slice_id / 2) -1] = (self.laterality, image)
                            # volume_array_dict[volume_string][int(chunk.slice_id / 2) -1] = image
                        else:
                            print('Failed to save image data for volume {}'.format(volume_string))
                    elif chunk.ind == 1:  # oct data
                        all_bits = [f.read(2) for i in range(image_data.height * image_data.width)]
                        raw_volume = list(map(self.read_custom_float, all_bits))
                        image = np.array(raw_volume).reshape(image_data.width, image_data.height)
                        image = 256 * pow(image, 1.0 / 2.4)
                        volume_string = '{}_{}_{}'.format(chunk.patient_id, chunk.study_id, chunk.series_id)
                        # print("oct volume string ", volume_string)
                        if volume_string in volume_array_dict.keys():
                            volume_array_dict[volume_string][int(chunk.slice_id / 2) - 1] = image
                        else:
                            print('Failed to save image data for volume {}'.format(volume_string))
                    else:
                        print("unrecognised chunk")

            oct_volumes = []
            for key, volume in volume_array_dict.items():
                if self.imagetype == "Fundus Autofluorescence":
                    try:
                        for lat, vol in volume:
                            oct_volumes.append(OCTVolumeWithMetaData(volume=[vol], laterality=lat, patient_id=key))
                    except (TypeError, ValueError) as e:
                        print("error: {}, volume not iteratable".format(e))
                        self.logger.warning("error: {}, volume not iteratable".format(e))
                else:
                    lat = fundus_images[key][0]
                    print("key {}, laterality {}".format(key, lat))
                    oct_volumes.append(OCTVolumeWithMetaData(volume=volume, laterality=lat, patient_id=key))

        return oct_volumes, fundus_images

    def read_custom_float(self, bytes):
        """ Implementation of bespoke float type used in .e2e files.

        Notes:
            Custom float is a floating point type with no sign, 6-bit exponent, and 10-bit mantissa.

        Args:
            bytes (str): The two bytes.

        Returns:
            float
        """
        power = pow(2, 10)
        # convert two bytes to 16-bit binary representation
        bits = bin(bytes[0])[2:].zfill(8)[::-1] + bin(bytes[1])[2:].zfill(8)[::-1]

        # get mantissa and exponent
        mantissa = bits[:10]
        exponent = bits[10:]

        # convert to decimal representations
        mantissa_sum = 1 + int(mantissa, 2) / power
        exponent_sum = int(exponent[::-1], 2) - 63
        decimal_value = mantissa_sum * pow(2, exponent_sum)
        return decimal_value
