import numpy as np
from tensorflow.keras.preprocessing import image

class Predictor:
    def __init__(self, model, class_names, img_size=(160, 160)):
        self.model = model
        self.class_names = class_names
        self.img_size = img_size

    def predict_image(self, image_path):
        img = image.load_img(image_path, target_size=self.img_size)
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        predictions = self.model.predict(img_array, verbose=0)
        predicted_index = np.argmax(predictions[0])
        predicted_class = self.class_names[predicted_index]
        confidence = float(predictions[0][predicted_index])

        return predicted_class, confidence
