#!/usr/bin/env python
import os

import numpy as np
import cv2 as cv

import keras
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
from keras import backend as K

from random import shuffle

class Patched_CNN(object):
    """
    Implementation of 'Patched CNN' architecture from
    http://chenpingyu.org/docs/yago_eccv2016.pdf (page 9)

    CNN that accepts 4 channels; Red, Green, Blue and Patch.
    Here, Patch is meant to be a mask which specifies if the pixel is part the
    the segment being classified, or just from a neighbouring segment.
    """
    def __init__(self):
        super(Patched_CNN, self).__init__()
        self.model = Sequential()

    def load_model(self, filepath='model.h5', custom_objects=None, compile=True):
        """ Load a model from 'filepath'. """
        self.model = keras.models.load_model(filepath, custom_objects, compile)

    def save_model(self, filepath='model.h5'):
        """ Save the current model as 'filepath'. """
        self.model.save(filepath)

    def build_model(self):
        """ Initialize an untrained model. """

        padding = "same"
        padding = "valid"

        # 32x32x4 -> conv1 -> 30x30x50
        self.model.add( Conv2D( 50, activation="relu", kernel_size=(3, 3),
                                input_shape=(32, 32, 4), padding=padding ))

        # 30x30x50 -> conv2 -> 28x28x50
        self.model.add( Conv2D( 50, kernel_size=(3, 3), activation="relu", padding=padding ) )

        # 28x28x50 -> pool1 -> 14x14x50
        self.model.add( MaxPooling2D( pool_size=(2, 2), strides=1))

        # 14x14x50 -> conv3 -> 12x12x50
        self.model.add( Conv2D( 50, kernel_size=(3, 3), activation="relu", padding=padding ) )

        # 12x12x50 -> conv4 -> 10x10x50
        self.model.add( Conv2D( 50, kernel_size=(3, 3), activation="relu", padding=padding ) )

        # 10x10x50 -> conv5 -> 10x10x30
        self.model.add( Conv2D( 30, kernel_size=(1, 1), activation="relu", padding=padding ) )

        # 10x10x30 -> pool2 -> 5x5x30
        self.model.add( MaxPooling2D( pool_size=(2, 2), strides=1 ))

        # 5x5x30 -> conv6 -> 3x3x50
        self.model.add( Conv2D( 50, kernel_size=(3, 3), activation="relu", padding=padding ) )

        # 3x3x50 -> flatten -> 450
        self.model.add( Flatten() )

        # 450 -> Dense Layer -> 1
        # self.model.add( Dense( 450, activation="relu"  ) )
        self.model.add( Dropout(0.5) )
        self.model.add( Dense( 1, activation="sigmoid") )

        def nll1(y_true, y_pred):
            """Negative log likelihood:
            Keras binary cross-entropy loss
            """
            # keras.losses.binary_crossentropy give the mean
            # over the last axis. we require the sum
            return K.sum(K.binary_crossentropy(y_true, y_pred), axis=-1)


        def nll2(y_true, y_pred):
            """
            Negative log likelihood:
            Numerical instability of Bernoulli with probabilities (probs)
            """
            likelihood = K.tf.distributions.Bernoulli(probs=y_pred)
            return - K.sum(likelihood.log_prob(y_true), axis=-1)

        def nll3(y_true, y_pred):
            """
            Negative log likelihood:
            Bernoulli with sigmoid log-odds (logits)
            """
            likelihood = K.tf.distributions.Bernoulli(logits=y_pred)
            return - K.sum(likelihood.log_prob(y_true), axis=-1)

        self.model.compile(
                # keras.optimizers.SGD(0.01),
                keras.optimizers.RMSprop(0.01),
                loss=keras.losses.binary_crossentropy,
                metrics=["accuracy"]
                )

    def train(self, image_segments, labels, batch_size=32, epochs=10, patience=2):
        """ Train a model using a arrays of input and output. """
        self.model.fit(
                np.array(image_segments),
                np.array(labels),
                batch_size,
                epochs,
                validation_split=0.33,
                callbacks=[
                        EarlyStopping(patience=patience),
                        ModelCheckpoint(
                            "./checkpoints/weights.{epoch:02d}-{val_acc:.2f}.hdf5",
                            monitor="val_acc",
                            verbose=1,
                            save_best_only=True)
                    ]
                )
        return
    def predict(self, imgs):
        return self.model.predict(imgs)

def open_images(path, max=None, size=(32, 32)):
    """ Read images under the directory given in 'path'. """
    print("- Loading images from", path)
    for (dirpath, dirnames, filenames) in os.walk(path):
        if max is not None:
            shuffle(filenames)
            filenames = filenames[:max]
            print("-- limited to reading", max, "files.")
        images = [
                    cv.resize(cv.imread(os.path.join(path, fname),
                                        cv.IMREAD_UNCHANGED)/255.0, size)
                    for fname in filenames
                ]
    # print(filenames)
    print("- Finished loading images from", path)
    return images

if __name__ == '__main__':

    shadows = open_images("./segments/shadows")
    non_shadows = open_images("./segments/non_shadows", len(shadows))

    x = [] # input features.
    y = [] # labels

    x.extend(shadows)
    x.extend(non_shadows)

    y.extend([ 1 for i in range(len(shadows)) ])
    y.extend([ 0 for i in range(len(non_shadows)) ])

    cnn = Patched_CNN()
    cnn.build_model()
    cnn.train(x, y, 100, 10, 2)
    cnn.save_model()
