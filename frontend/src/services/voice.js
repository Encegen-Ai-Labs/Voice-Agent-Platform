import API from "./api";

export const getVoices = async () => {
    const response = await API.get("/voices");
    return response.data;
};