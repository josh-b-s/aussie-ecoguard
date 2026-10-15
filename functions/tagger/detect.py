import boto3

rekognition = boto3.client("rekognition")


def detect_tags(image, config):
    """Return {tag: count} for one image.

    image is a Rekognition Image dict: {"Bytes": ...} or {"S3Object": {...}}.
    """
    # No MinConfidence here: weak labels still carry boxes that the animal count needs
    labels = rekognition.detect_labels(Image=image)["Labels"]
    species = species_present(labels, config)
    species = drop_overridden(species, config.get("drop_if_present", {}))
    return count_species(species, labels, config["label_map"])


def species_present(labels, config):
    return {
        config["label_map"][label["Name"]]
        for label in labels
        if label["Name"] in config["label_map"]
        and label["Confidence"] >= config["min_confidence"]
    }


def drop_overridden(species, rules):
    """Remove a tag when a more specific one is present, e.g. {"dog": ["fox"]}.

    Rekognition also calls foxes dogs and cats, so those tags would otherwise appear on fox photos.
    """
    return {
        tag
        for tag in species
        if not any(blocker in species for blocker in rules.get(tag, []))
    }


def count_species(species, labels, label_map):
    if len(species) == 1:
        # Rekognition's boxes are reliable but their species labels are not, so one species
        # takes every animal box in the image. Unmapped animals in frame inflate the count.
        total = animal_boxes(labels)
        return {tag: max(total, 1) for tag in species}
    # With several species the box labels can't be split between them, so use each
    # species' own boxes. This can undercount.
    return {tag: max(own_boxes(tag, labels, label_map), 1) for tag in species}


def animal_boxes(labels):
    return sum(len(label["Instances"]) for label in labels if is_animal_box(label))


def is_animal_box(label):
    return any(parent["Name"] == "Animal" for parent in label.get("Parents", []))


def own_boxes(tag, labels, label_map):
    # Take the max, not the sum: Pig, Boar and Hog boxes can sit on the same animal
    return max(
        (len(label["Instances"]) for label in labels if label_map.get(label["Name"]) == tag),
        default=0,
    )


def merge_max(per_frame_tags):
    """Combine frame results by taking the highest count seen per tag."""
    merged = {}
    for tags in per_frame_tags:
        for tag, count in tags.items():
            merged[tag] = max(merged.get(tag, 0), count)
    return merged