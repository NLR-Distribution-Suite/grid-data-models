# CIM vs GDM a comparison

The common information model (CIM) as defined by the International Electrotechnical Commission (IEC) as "An abstract model that represents all the major objects in an electric utility enterprise typically involved in utility operations". It provides a standard way of defining object classes, their attributes and relationships. The CIM is currently maintained as UML model. 

## Need for Language Specific Data Models

Developers often require from common data structures and models to exchange data and aid interoperability between applications. Language-specific data models have many advantages in development environments where a common programming language is used and where large amounts of data handling require extensive validation. Standard schemas such as the JSON schema offer some basic validation, but more complex validation tasks often require language specific implementation. A language specific data model can perform common validation tasks that are needed by all applications in the development environment. For instance, we identified several challenges with using the CIM standard as the data model for applications in our development environment.

## Challenges in  CIM and Need for GDM

* `Lack of cross object validation: ` Validating CIM compatible power system data requires external script not tied to the data model. For example, on distribution networks, a three phase load should not be attached to a single phase line. Language-specific data models allow for validation of this type of model requirement during the construction of the model, and it ensures that all applications using the data model have a common model representation.

* `Lack of unit conversion for power system quantities`: Different applications use different unit representations, but unit conversion outside of the data model can introduce errors. Language specific data models can handle unit representation and avoid unit conversion errors.

* `Complexity involved in creating language specific data models:` We have not identified robust methods for translating CIM into language specific data models. There are methods to autogenerate language specific data models from CIM, but these methods lack object type enforcement and the extensive validation capabilities needed for data intensive models.

In grid data models, we are attempting to solve these challenges. GDM is a collection of [pydantic](https://docs.pydantic.dev/latest/) data models (Pydantic is a third party package for defining data model along with validation logic) for representing power distribution assets.

## Limitations of GDM

* GDM currently is only supported in [Python](https://python.org) programming language. 

* It is still in development phase and may not have representation for all the distribution assets you see in CIM.
